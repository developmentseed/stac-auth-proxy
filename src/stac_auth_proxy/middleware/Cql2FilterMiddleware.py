from logging import getLogger
import json
from dataclasses import dataclass
from typing import Annotated, Callable, Optional

from cql2 import Expr
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.requests import Request

from ..config import EndpointMethods
from ..utils import di, filters, requests

logger = getLogger(__name__)

FILTER_STATE_KEY = "cql2_filter"


@dataclass(frozen=True)
class BuildCql2FilterMiddleware:
    """Middleware to build the Cql2Filter."""

    app: ASGIApp

    # Filters
    collections_filter: Optional[Callable] = None
    items_filter: Optional[Callable] = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)

        filter_builder = self._get_filter(request.url.path)
        if not filter_builder:
            return await self.app(scope, receive, send)

        async def set_filter(body: Optional[dict] = None) -> None:
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
                    **request.state._state,
                }
            )
            cql2_filter.validate()
            scope["state"][FILTER_STATE_KEY] = cql2_filter

        # For GET requests, we can build the filter immediately
        # NOTE: It appears that FastAPI will not call receive function for GET requests
        if request.method == "GET":
            await set_filter()
            return await self.app(scope, receive, send)

        total_body = b""

        async def receive_build_filter() -> Message:
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
            # TODO: Use collections_filter_endpoints & items_filter_endpoints
            (filters.is_collection_endpoint, self.collections_filter),
            (filters.is_item_endpoint, self.items_filter),
            (filters.is_search_endpoint, self.items_filter),
        ]
        for check, builder in endpoint_filters:
            if check(path):
                return builder
        return None


@dataclass(frozen=True)
class ApplyCql2FilterMiddleware:
    """Middleware to apply the Cql2Filter to the request."""

    app: ASGIApp

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Add the Cql2Filter to the request."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)

        if request.method == "GET":
            cql2_filter = scope["state"].get(FILTER_STATE_KEY)
            if cql2_filter:
                scope["query_string"] = filters.append_qs_filter(
                    request.url.query, cql2_filter
                )
            return await self.app(scope, receive, send)
        elif request.method in ["POST", "PUT", "PATCH"]:
            # For methods with bodies, we need to wrap receive to modify the body
            async def receive_with_filter() -> Message:
                message = await receive()
                if message["type"] != "http.request":
                    return message

                cql2_filter = scope["state"].get(FILTER_STATE_KEY)
                if cql2_filter:
                    try:
                        body = message.get("body", b"{}")
                    except json.JSONDecodeError as e:
                        logger.warning("Failed to parse request body as JSON")
                        # TODO: Return a 400 error
                        raise e

                    new_body = filters.append_body_filter(json.loads(body), cql2_filter)
                    message["body"] = json.dumps(new_body).encode("utf-8")
                return message

            return await self.app(scope, receive_with_filter, send)

        return await self.app(scope, receive, send)
