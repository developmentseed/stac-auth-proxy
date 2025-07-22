"""Middleware to inject CQL2 filters into the query string for GET/list endpoints."""

import re
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
class Cql2ApplyFilterQueryStringMiddleware:
    """Middleware to inject CQL2 filters into the query string for GET/list endpoints."""

    app: ASGIApp
    state_key: str = "cql2_filter"

    single_record_endpoints = [
        r"^/collections/([^/]+)/items/([^/]+)$",
        r"^/collections/([^/]+)$",
    ]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Apply the CQL2 filter to the query string."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)
        cql2_filter: Optional[Expr] = getattr(request.state, self.state_key, None)
        if not cql2_filter:
            return await self.app(scope, receive, send)

        # Only handle GET requests that are not single-record endpoints
        if request.method != "GET":
            return await self.app(scope, receive, send)
        if any(
            re.match(expr, request.url.path) for expr in self.single_record_endpoints
        ):
            return await self.app(scope, receive, send)

        # Inject filter into query string
        scope = dict(scope)
        scope["query_string"] = filters.append_qs_filter(request.url.query, cql2_filter)
        return await self.app(scope, receive, send)
