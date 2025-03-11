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

        total_body = b""

        async def receive_build_filter() -> Message:
            nonlocal total_body

            message = await receive()
            total_body += message.get("body", b"")

            if not message.get("more_body"):
                request = Request(scope)
                filter_builder = self._get_filter(request.url.path)
                if filter_builder:
                    cql2_filter = await filter_builder(
                        {
                            "req": {
                                "path": request.url.path,
                                "method": request.method,
                                "query_params": dict(request.query_params),
                                "path_params": requests.extract_variables(
                                    request.url.path
                                ),
                                "headers": dict(request.headers),
                                "body": json.loads(total_body),
                            },
                            **request.state._state,
                        }
                    )
                    cql2_filter.validate()
                    scope["state"][FILTER_STATE_KEY] = cql2_filter
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

        async def apply_filter() -> Message:
            message = await receive()
            request = Request(scope)
            cql2_filter = getattr(request.state, FILTER_STATE_KEY, None)
            if not cql2_filter:
                logger.debug("No cql2 filter found on message.")
                return message

            if request.method == "GET":
                query = filters.insert_qs_filter(qs=query, filter=cql2_filter)
                # Get the original query string
                original_qs = scope["query_string"].decode("utf-8")
                # Apply the filter to query string
                new_qs = filters.append_qs_filter(original_qs, cql2_filter)
                # Update the scope with new query string
                # scope["query_string"] = new_qs.encode("utf-8")
            elif request.method in ["POST", "PUT", "PATCH"]:
                # TODO: Apply the filter to the body
                message["body"] = json.dumps(
                    filters.append_body_filter(
                        body=json.loads(message.get("body", "{}")),
                        filter=cql2_filter,
                    )
                ).encode("utf-8")

            return message

        return await self.app(scope, apply_filter, send)
