"""Middleware to validate the response body with a CQL2 filter for single-record endpoints."""

import json
import re
from dataclasses import dataclass
from logging import getLogger
from typing import Optional

from cql2 import Expr
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..utils.middleware import required_conformance

logger = getLogger(__name__)


@required_conformance(
    r"http://www.opengis.net/spec/cql2/1.0/conf/basic-cql2",
    r"http://www.opengis.net/spec/cql2/1.0/conf/cql2-text",
    r"http://www.opengis.net/spec/cql2/1.0/conf/cql2-json",
)
@dataclass
class Cql2ValidateResponseBodyMiddleware:
    """ASGI middleware to validate the response body with a CQL2 filter for single-record endpoints."""

    app: ASGIApp
    state_key: str = "cql2_filter"

    single_record_endpoints = [
        r"^/collections/([^/]+)/items/([^/]+)$",
        r"^/collections/([^/]+)$",
    ]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Validate the response body with a CQL2 filter for single-record endpoints."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)
        cql2_filter: Optional[Expr] = getattr(request.state, self.state_key, None)
        if not cql2_filter:
            return await self.app(scope, receive, send)

        if not any(
            re.match(expr, request.url.path) for expr in self.single_record_endpoints
        ):
            return await self.app(scope, receive, send)

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
                        response_start, body_chunks, send, cql2_filter
                    )
            else:
                await send(message)

        await self.app(scope, receive, send_wrapper)

    async def _process_and_send_response(
        self, response_start, body_chunks, send, cql2_filter
    ):
        body = b"".join(body_chunks)
        try:
            body_json = json.loads(body)
        except json.JSONDecodeError:
            logger.warning("Failed to parse response body as JSON")
            await self._send_json_response(
                send,
                status=502,
                content={
                    "code": "ParseError",
                    "description": "Failed to parse response body as JSON",
                },
            )
            return

        try:
            cql2_matches = cql2_filter.matches(body_json)
        except Exception as e:
            cql2_matches = False
            logger.warning("Failed to apply filter: %s", e)

        if cql2_matches:
            logger.debug("Response matches filter, returning record")
            # Send the original response start
            await send(response_start)
            # Send the filtered body
            await send(
                {
                    "type": "http.response.body",
                    "body": json.dumps(body_json).encode("utf-8"),
                    "more_body": False,
                }
            )
        else:
            logger.debug("Response did not match filter, returning 404")
            await self._send_json_response(
                send,
                status=404,
                content={"code": "NotFoundError", "description": "Record not found."},
            )

    async def _send_json_response(self, send, status, content):
        response_bytes = json.dumps(content).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(response_bytes)).encode("latin1")),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": response_bytes,
                "more_body": False,
            }
        )
