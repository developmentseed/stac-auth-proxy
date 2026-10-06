"""Middleware to inject CQL2 filters into the query string for GET/list endpoints."""

from dataclasses import dataclass
from logging import getLogger
from typing import Optional

from cql2 import Expr
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from ..utils import filters
from ..utils.middleware import bad_request, required_conformance
from ..utils.requests import match_path

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
            match_path(expr, request.url.path) for expr in self.single_record_endpoints
        ):
            return await self.app(scope, receive, send)

        # Inject filter into query string
        try:
            query_string = filters.append_qs_filter(
                scope.get("query_string", b""), cql2_filter
            )
        except filters.InvalidFilterRequestError as e:
            return await bad_request(str(e))(scope, receive, send)
        scope = dict(scope)
        scope["query_string"] = query_string
        return await self.app(scope, receive, send)
