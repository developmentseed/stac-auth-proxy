"""Middleware to build the Cql2Filter."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from cql2 import Expr, ValidationError
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from ..utils import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BuildCql2FilterMiddleware:
    """Middleware to build the Cql2Filter."""

    app: ASGIApp

    state_key: str = "cql2_filter"

    # Filters
    collections_filter: Optional[Callable] = None
    collections_filter_path: str = r"^/collections(/[^/]+)?$"
    items_filter: Optional[Callable] = None
    items_filter_path: str = r"^(/collections/([^/]+)/items(/[^/]+)?$|/search$)"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Build the CQL2 filter, place on the request state."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)

        filter_builder = self._get_filter(request.url.path)
        if not filter_builder:
            return await self.app(scope, receive, send)

        filter_expr = await filter_builder(
            {
                "req": {
                    "path": request.url.path,
                    "method": request.method,
                    "query_params": dict(request.query_params),
                    "path_params": requests.extract_variables(request.url.path),
                    "headers": dict(request.headers),
                },
                **scope["state"],
            }
        )
        cql2_filter = Expr(filter_expr)
        try:
            cql2_filter.validate()
        except ValidationError:
            logger.error("Invalid CQL2 filter: %s", filter_expr)
            return await Response(status_code=502, content="Invalid CQL2 filter")
        setattr(request.state, self.state_key, cql2_filter)

        return await self.app(scope, receive, send)

    def _get_filter(
        self, path: str
    ) -> Optional[Callable[..., Awaitable[str | dict[str, Any]]]]:
        """Get the CQL2 filter builder for the given path."""
        endpoint_filters = [
            (self.collections_filter_path, self.collections_filter),
            (self.items_filter_path, self.items_filter),
        ]
        for expr, builder in endpoint_filters:
            if re.match(expr, path):
                return builder
        return None
