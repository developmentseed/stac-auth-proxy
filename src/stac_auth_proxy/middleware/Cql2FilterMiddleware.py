import json
from dataclasses import dataclass
from typing import Annotated, Callable, Optional

from cql2 import Expr
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.requests import Request

from ..config import EndpointMethods
from ..utils import di, filters, requests


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
        if filter_builder:
            cql2_filter = await di.call_with_injected_dependencies(
                func=filter_builder,
                request=request,
            )
            cql2_filter.validate()
            scope["state"][FILTER_STATE_KEY] = cql2_filter

        return await self.app(scope, receive, send)

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
    """Middleware to add the OpenAPI spec to the response."""

    app: ASGIApp

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Add the Cql2Filter to the request."""
        request = Request(scope)
        cql2_filter = request.state.get(FILTER_STATE_KEY)

        if scope["type"] != "http" or not cql2_filter:
            return await self.app(scope, receive, send)

        # Apply filter if applicable

        total_body = b""

        async def receive_with_filter(message: Message):
            query = request.url.query

            # TODO: How do we handle querystrings in middleware?
            if request.method == "GET":
                query = filters.insert_qs_filter(qs=query, filter=cql2_filter)

            if message["type"] == "http.response.body":
                nonlocal total_body
                total_body += message["body"]
                if message["more_body"]:
                    return await receive({**message, "body": b""})

                # TODO: Only on search, not on create or update...
                if request.method in ["POST", "PUT"]:
                    return await receive(
                        {
                            "type": "http.response.body",
                            "body": requests.dict_to_bytes(
                                filters.append_body_filter(
                                    json.loads(total_body), cql2_filter
                                )
                            ),
                            "more_body": False,
                        }
                    )

                return await receive(message)

            await receive(message)

        return await self.app(scope, receive_with_filter, send)
