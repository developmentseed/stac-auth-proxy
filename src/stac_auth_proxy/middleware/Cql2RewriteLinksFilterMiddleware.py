"""Middleware to rewrite 'filter' in .links of the JSON response, removing the filter from the request state."""

import json
from dataclasses import dataclass
from logging import getLogger
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from cql2 import Expr
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = getLogger(__name__)

_UNSET: Any = object()


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
        original_filter = request.query_params.get("filter")
        cql2_filter: Optional[Expr] = getattr(request.state, self.state_key, None)
        if cql2_filter is None:
            # No filter set, just pass through
            return await self.app(scope, receive, send)

        # When the client sends the filter in the request body (POST /search etc.),
        # query_params won't expose it. Capture it here so we can put it back on
        # paginated next-link bodies. We use a sentinel to distinguish "client sent
        # no filter" (drop the field) from "client sent some filter value" (echo it
        # back verbatim). Mirroring the query-string read above, we attempt this
        # for any method that can carry a body and let the JSON-decode no-op when
        # the body is absent or unparseable.
        original_body_filter: Any = _UNSET
        original_body_filter_lang: Any = _UNSET

        if request.method in ("POST", "PUT", "PATCH"):
            buffered_body = b""
            more_body = True
            while more_body:
                message = await receive()
                if message["type"] == "http.request":
                    buffered_body += message.get("body", b"")
                    more_body = message.get("more_body", False)
                else:
                    # Disconnect or unexpected message; bail out without capture.
                    break

            try:
                body_json = json.loads(buffered_body) if buffered_body else None
            except json.JSONDecodeError:
                body_json = None

            if isinstance(body_json, dict):
                if "filter" in body_json:
                    original_body_filter = body_json["filter"]
                if "filter-lang" in body_json:
                    original_body_filter_lang = body_json["filter-lang"]

            replayed = False

            async def replay_receive() -> Message:
                nonlocal replayed
                if not replayed:
                    replayed = True
                    return {
                        "type": "http.request",
                        "body": buffered_body,
                        "more_body": False,
                    }
                return await receive()

            receive = replay_receive

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
                        response_start,
                        body_chunks,
                        send,
                        original_filter,
                        original_body_filter,
                        original_body_filter_lang,
                    )
            else:
                await send(message)

        await self.app(scope, receive, send_wrapper)

    async def _process_and_send_response(
        self,
        response_start: Message,
        body_chunks: list[bytes],
        send: Send,
        original_filter: Optional[str],
        original_body_filter: Any = _UNSET,
        original_body_filter_lang: Any = _UNSET,
    ):
        body = b"".join(body_chunks)
        try:
            data = json.loads(body)
        except Exception:
            await send(response_start)
            await send({"type": "http.response.body", "body": body, "more_body": False})
            return

        cql2_filter = Expr(original_filter) if original_filter else None
        links = data.get("links")
        if isinstance(links, list):
            for link in links:
                # Handle filter in query string
                if "href" in link:
                    url = urlparse(link["href"])
                    qs = parse_qs(url.query)
                    if "filter" in qs:
                        if cql2_filter:
                            qs["filter"] = [cql2_filter.to_text()]
                        else:
                            qs.pop("filter", None)
                            qs.pop("filter-lang", None)
                        new_query = urlencode(qs, doseq=True)
                        link["href"] = urlunparse(url._replace(query=new_query))

                # Handle filter in body (for POST links)
                if "body" in link and isinstance(link["body"], dict):
                    had_filter = "filter" in link["body"]

                    if original_body_filter is not _UNSET:
                        # Client originally sent a CQL2 filter in the request
                        # body (POST /search). Echo it back verbatim so
                        # paginated requests carry the same filter shape and
                        # serialization.
                        link["body"]["filter"] = original_body_filter
                    elif had_filter and cql2_filter:
                        # Filter came from the query string; emit it in the
                        # body as JSON so the next-link POST is self-contained.
                        link["body"]["filter"] = cql2_filter.to_json()
                    elif had_filter:
                        link["body"].pop("filter", None)

                    if original_body_filter_lang is not _UNSET:
                        link["body"]["filter-lang"] = original_body_filter_lang
                    elif had_filter and not cql2_filter:
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
