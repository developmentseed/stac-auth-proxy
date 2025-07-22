"""Middleware to augment the request body with a CQL2 filter for POST/PUT/PATCH requests."""

import json
from dataclasses import dataclass
from logging import getLogger
from typing import Optional

from cql2 import Expr
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from ..utils import filters
from ..utils.middleware import required_conformance

logger = getLogger(__name__)


@required_conformance(
    r"http://www.opengis.net/spec/cql2/1.0/conf/basic-cql2",
    r"http://www.opengis.net/spec/cql2/1.0/conf/cql2-text",
    r"http://www.opengis.net/spec/cql2/1.0/conf/cql2-json",
)
@dataclass(frozen=True)
class Cql2ApplyFilterBodyMiddleware:
    """Middleware to augment the request body with a CQL2 filter for POST/PUT/PATCH requests."""

    app: ASGIApp
    state_key: str = "cql2_filter"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Apply the CQL2 filter to the request body."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)
        cql2_filter: Optional[Expr] = getattr(request.state, self.state_key, None)
        if not cql2_filter:
            return await self.app(scope, receive, send)

        if request.method not in ["POST", "PUT", "PATCH"]:
            return await self.app(scope, receive, send)

        body = b""
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                more_body = message.get("more_body", False)

        try:
            body_json = json.loads(body) if body else {}
        except json.JSONDecodeError:
            logger.warning("Failed to parse request body as JSON")
            from starlette.responses import JSONResponse

            response = JSONResponse(
                {
                    "code": "ParseError",
                    "description": "Request body must be valid JSON.",
                },
                status_code=400,
            )
            await response(scope, receive, send)
            return

        if not isinstance(body_json, dict):
            logger.warning("Request body must be a JSON object")
            from starlette.responses import JSONResponse

            response = JSONResponse(
                {
                    "code": "TypeError",
                    "description": "Request body must be a JSON object.",
                },
                status_code=400,
            )
            await response(scope, receive, send)
            return

        new_body = json.dumps(
            filters.append_body_filter(body_json, cql2_filter)
        ).encode("utf-8")

        # Patch content-length in the headers
        headers = dict(scope["headers"])
        headers[b"content-length"] = str(len(new_body)).encode("latin1")
        scope = dict(scope)
        scope["headers"] = list(headers.items())

        async def new_receive():
            return {
                "type": "http.request",
                "body": new_body,
                "more_body": False,
            }

        await self.app(scope, new_receive, send)
