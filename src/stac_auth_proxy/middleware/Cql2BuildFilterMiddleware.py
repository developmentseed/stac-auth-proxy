"""Middleware to build the Cql2Filter."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, Sequence, Union

from cql2 import Expr, ValidationError
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ..utils import requests
from ..utils.middleware import required_conformance

logger = logging.getLogger(__name__)


@required_conformance(
    "http://www.opengis.net/spec/cql2/1.0/conf/basic-cql2",
    "http://www.opengis.net/spec/cql2/1.0/conf/cql2-text",
    "http://www.opengis.net/spec/cql2/1.0/conf/cql2-json",
)
@dataclass(frozen=True)
class Cql2BuildFilterMiddleware:
    """Middleware to build the Cql2Filter."""

    app: ASGIApp

    state_key: str = "cql2_filter"

    # Filters
    collections_filter: Optional[Callable] = None
    collections_filter_path: Union[str, Sequence[str]] = (
        r"^/collections(?:/(?P<collection_id>[^/]+))?$",
    )
    items_filter: Optional[Callable] = None
    items_filter_path: Union[str, Sequence[str]] = (
        r"^(?:/collections/(?P<collection_id>[^/]+)/items(?:/(?P<item_id>[^/]+))?|/search)$",
    )

    def __post_init__(self):
        """Set required conformances based on the filter functions."""
        for attr in ("collections_filter_path", "items_filter_path"):
            object.__setattr__(self, attr, requests.as_patterns(getattr(self, attr)))
            for pattern in getattr(self, attr):
                if not re.compile(pattern).groupindex:
                    logger.info(
                        "Filter path %r declares no named capture groups, "
                        "falling back to built-in path param extraction.",
                        pattern,
                    )

        required_conformances = set()
        if self.collections_filter:
            logger.debug("Appending required conformance for collections filter")
            # https://github.com/stac-api-extensions/collection-search/blob/4825b4b1cee96bdc0cbfbb342d5060d0031976f0/README.md#L5
            required_conformances.update(
                [
                    "https://api.stacspec.org/v1.0.0/core",
                    r"https://api.stacspec.org/v1\.0\.0(?:-[\w\.]+)?/collection-search",
                    r"https://api.stacspec.org/v1\.0\.0(?:-[\w\.]+)?/collection-search#filter",
                    "http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/simple-query",
                ]
            )
        if self.items_filter:
            logger.debug("Appending required conformance for items filter")
            # https://github.com/stac-api-extensions/filter/blob/c763dbbf0a52210ab8d9866ff048da448d270f93/README.md#conformance-classes
            required_conformances.update(
                [
                    "http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/filter",
                    "http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/features-filter",
                    r"https://api.stacspec.org/v1\.0\.0(?:-[\w\.]+)?/item-search#filter",
                ]
            )

        # Must set required conformances on class
        self.__class__.__required_conformances__ = required_conformances.union(
            getattr(self.__class__, "__required_conformances__", [])
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Build the CQL2 filter, place on the request state."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)

        if request.method.upper() == "OPTIONS":
            logger.debug("Skipping CQL2 filter build for OPTIONS request")
            return await self.app(scope, receive, send)

        filter_builder, path_params = self._get_filter(request.url.path)
        if not filter_builder:
            return await self.app(scope, receive, send)

        try:
            filter_expr = await filter_builder(
                {
                    "req": {
                        "path": request.url.path,
                        "method": request.method,
                        "query_params": dict(request.query_params),
                        "path_params": path_params,
                        "headers": dict(request.headers),
                    },
                    **scope["state"],
                }
            )
        except HTTPException as e:
            response = JSONResponse({"detail": e.detail}, status_code=e.status_code)
            return await response(scope, receive, send)

        cql2_filter = Expr(filter_expr)
        try:
            cql2_filter.validate()
        except ValidationError:
            logger.error("Invalid CQL2 filter: %s", filter_expr)
            response = JSONResponse({"detail": "Invalid CQL2 filter"}, status_code=502)
            return await response(scope, receive, send)

        setattr(request.state, self.state_key, cql2_filter)

        return await self.app(scope, receive, send)

    def _get_filter(
        self, path: str
    ) -> tuple[Optional[Callable[..., Awaitable[str | dict[str, Any]]]], dict]:
        """Get the CQL2 filter builder for the given path and its path params."""
        endpoint_filters = [
            (self.collections_filter_path, self.collections_filter),
            (self.items_filter_path, self.items_filter),
        ]
        for patterns, builder in endpoint_filters:
            for expr in patterns:
                match = re.match(expr, path)
                if match:
                    return builder, self._path_params(match, path)
        return None, {}

    @staticmethod
    def _path_params(match: re.Match, path: str) -> dict:
        """Get the path params declared by a matched pattern's named groups."""
        if match.re.groupindex:
            return {k: v for k, v in match.groupdict().items() if v is not None}
        return requests.extract_variables(path)
