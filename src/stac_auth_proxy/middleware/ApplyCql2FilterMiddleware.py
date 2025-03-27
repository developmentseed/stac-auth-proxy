"""Middleware to apply CQL2 filters."""

import json
from dataclasses import dataclass
from logging import getLogger

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..utils import filters

logger = getLogger(__name__)


@dataclass(frozen=True)
class ApplyCql2FilterMiddleware:
    """Middleware to apply the Cql2Filter to the request."""

    app: ASGIApp

    state_key: str = "cql2_filter"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Add the Cql2Filter to the request."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)

        if request.method == "GET":
            cql2_filter = getattr(request.state, self.state_key, None)
            if cql2_filter:
                scope["query_string"] = filters.append_qs_filter(
                    request.url.query, cql2_filter
                )
            return await self.app(scope, receive, send)

        elif request.method in ["POST", "PUT", "PATCH"]:

            async def receive_and_apply_filter() -> Message:
                message = await receive()
                if message["type"] != "http.request":
                    return message

                cql2_filter = getattr(request.state, self.state_key, None)
                if cql2_filter:
                    try:
                        body = json.loads(message.get("body", b"{}"))
                    except json.JSONDecodeError as e:
                        logger.warning("Failed to parse request body as JSON")
                        # TODO: Return a 400 error
                        raise e

                    new_body = filters.append_body_filter(body, cql2_filter)
                    message["body"] = json.dumps(new_body).encode("utf-8")
                return message

            return await self.app(scope, receive_and_apply_filter, send)

        return await self.app(scope, receive, send)
