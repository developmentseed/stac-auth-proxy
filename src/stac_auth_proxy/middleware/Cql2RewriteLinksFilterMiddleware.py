"""Middleware to rewrite 'filter' in .links of the JSON response, removing the filter from the request state."""

import json
from dataclasses import dataclass
from logging import getLogger
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from cql2 import Expr
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = getLogger(__name__)


@dataclass(frozen=True)
class Cql2RewriteLinksFilterMiddleware:
    """ASGI middleware to rewrite 'filter' in .links of the JSON response, removing the filter from the request state."""

    app: ASGIApp
    state_key: str = "cql2_filter"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Replace 'filter' in .links of the JSON response to state before we had applied the filter."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)
        cql2_filter: Optional[Expr] = getattr(request.state, self.state_key, None)
        if cql2_filter is None:
            # No filter set, just pass through
            return await self.app(scope, receive, send)

        user_filter, receive = await self._extract_user_filter(request, receive)

        # Intercept the response
        response_start = None
        body_chunks = []
        more_body = True

        async def send_wrapper(message: Message):
            nonlocal response_start, body_chunks, more_body
            if message["type"] == "http.response.start":
                response_start = message
            elif message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))
                more_body = message.get("more_body", False)
                if not more_body:
                    await self._process_and_send_response(
                        response_start, body_chunks, send, user_filter
                    )
            else:
                await send(message)

        await self.app(scope, receive, send_wrapper)

    async def _extract_user_filter(
        self, request: Request, receive: Receive
    ) -> tuple[Optional[Expr], Receive]:
        """
        Recover the user's original filter from either the query string or JSON body.

        For methods that may carry a JSON body (POST/PUT/PATCH), the body is buffered
        and a replacement ``receive`` is returned so downstream consumers still see it.
        """
        query_filter = request.query_params.get("filter")
        if query_filter:
            try:
                return Expr(query_filter), receive
            except Exception:
                logger.warning("Failed to parse user filter from query string")
                return None, receive

        if request.method not in ("POST", "PUT", "PATCH"):
            return None, receive

        body = b""
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                more_body = message.get("more_body", False)
            else:
                # e.g. http.disconnect - stop reading; downstream will get the same.
                break

        async def replay_receive() -> Message:
            return {"type": "http.request", "body": body, "more_body": False}

        if not body:
            return None, replay_receive

        try:
            body_json = json.loads(body)
        except json.JSONDecodeError:
            return None, replay_receive

        if not isinstance(body_json, dict):
            return None, replay_receive

        body_filter = body_json.get("filter")
        if body_filter is None:
            return None, replay_receive

        try:
            return Expr(body_filter), replay_receive
        except Exception:
            logger.warning("Failed to parse user filter from request body")
            return None, replay_receive

    async def _process_and_send_response(
        self,
        response_start: Message,
        body_chunks: list[bytes],
        send: Send,
        user_filter: Optional[Expr],
    ):
        body = b"".join(body_chunks)
        try:
            data = json.loads(body)
        except Exception:
            await send(response_start)
            await send({"type": "http.response.body", "body": body, "more_body": False})
            return

        links = data.get("links")
        if isinstance(links, list):
            for link in links:
                # Handle filter in query string
                if "href" in link:
                    url = urlparse(link["href"])
                    qs = parse_qs(url.query)
                    if "filter" in qs:
                        if user_filter is not None:
                            qs["filter"] = [user_filter.to_text()]
                        else:
                            qs.pop("filter", None)
                            qs.pop("filter-lang", None)
                        new_query = urlencode(qs, doseq=True)
                        link["href"] = urlunparse(url._replace(query=new_query))

                # Handle filter in body (for POST links). The spec only
                # requires cql2-json for POST bodies, but if the link advertises
                # cql2-text we preserve that lang on the way out.
                if "body" in link and isinstance(link["body"], dict):
                    if "filter" in link["body"]:
                        if user_filter is not None:
                            if link["body"].get("filter-lang") == "cql2-text":
                                link["body"]["filter"] = user_filter.to_text()
                            else:
                                link["body"]["filter"] = user_filter.to_json()
                        else:
                            link["body"].pop("filter", None)
                            link["body"].pop("filter-lang", None)

        # Send the modified response
        new_body = json.dumps(data).encode("utf-8")

        # Patch content-length
        headers = [
            (k, v) for k, v in response_start["headers"] if k != b"content-length"
        ]
        headers.append((b"content-length", str(len(new_body)).encode("latin1")))
        response_start = dict(response_start)
        response_start["headers"] = headers
        await send(response_start)
        await send({"type": "http.response.body", "body": new_body, "more_body": False})
