"""Middleware to build the Cql2Filter."""

import json
import re
from dataclasses import dataclass
from typing import Callable, Optional

from cql2 import Expr
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..utils import requests


@dataclass(frozen=True)
class BuildCql2FilterMiddleware:
    """Middleware to build the Cql2Filter."""

    app: ASGIApp

    state_key: str = "cql2_filter"

    # Filters
    collections_filter: Optional[Callable] = None
    items_filter: Optional[Callable] = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Build the CQL2 filter, place on the request state."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)

        filter_builder = self._get_filter(request.url.path)
        if not filter_builder:
            return await self.app(scope, receive, send)

        async def set_filter(body: Optional[dict] = None) -> None:
            assert filter_builder is not None
            cql2_filter = await filter_builder(
                {
                    "req": {
                        "path": request.url.path,
                        "method": request.method,
                        "query_params": dict(request.query_params),
                        "path_params": requests.extract_variables(request.url.path),
                        "headers": dict(request.headers),
                        "body": body,
                    },
                    **scope["state"],
                }
            )
            cql2_filter.validate()
            setattr(request.state, self.state_key, cql2_filter)

        # For GET requests, we can build the filter immediately
        if request.method == "GET":
            await set_filter()
            return await self.app(scope, receive, send)

        total_body = b""

        async def receive_build_filter() -> Message:
            """
            Receive the body of the request and build the filter.
            NOTE: This is not called for GET requests.
            """
            nonlocal total_body

            message = await receive()
            total_body += message.get("body", b"")

            if not message.get("more_body"):
                await set_filter(json.loads(total_body) if total_body else None)
            return message

        return await self.app(scope, receive_build_filter, send)

    def _get_filter(self, path: str) -> Optional[Callable[..., Expr]]:
        """Get the CQL2 filter builder for the given path."""
        endpoint_filters = [
            (r"^/collections(/[^/]+)?$", self.collections_filter),
            (r"^(/collections/([^/]+)/items(/[^/]+)?$|/search$)", self.items_filter),
        ]
        for expr, builder in endpoint_filters:
            if re.match(expr, path):
                return builder
        return None
