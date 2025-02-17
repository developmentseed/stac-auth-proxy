"""Tooling to manage the reverse proxying of requests to an upstream STAC API."""

import json
import logging
import time
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Optional

import httpx
from cql2 import Expr
from fastapi import Depends, Request
from starlette.background import BackgroundTask
from starlette.datastructures import MutableHeaders
from starlette.responses import StreamingResponse

from ..utils import di, filters

logger = logging.getLogger(__name__)


@dataclass
class ReverseProxyHandler:
    """Reverse proxy functionality."""

    upstream: str
    auth_dependency: Callable

    client: httpx.AsyncClient = None

    # Filters
    collections_filter: Optional[Callable] = None
    items_filter: Optional[Callable] = None

    def __post_init__(self):
        """Initialize the HTTP client."""
        self.client = self.client or httpx.AsyncClient(
            base_url=self.upstream,
            timeout=httpx.Timeout(timeout=15.0),
        )
        self.collections_filter = (
            self.collections_filter() if self.collections_filter else None
        )
        self.items_filter = self.items_filter() if self.items_filter else None

        # Inject auth dependency into filters
        for endpoint in [self.collections_filter, self.items_filter]:
            if not endpoint:
                continue
            endpoint.__annotations__["auth_token"] = Annotated[
                Optional[Expr],
                Depends(self.auth_dependency),
            ]

    def _get_filter(self, path: str) -> Optional[Callable[..., Expr]]:
        """Get the CQL2 filter builder for the given path."""
        endpoint_filters = [
            # TODO: Use collections_filter_endpoints & items_filter_endpoints
            (filters.is_collection_endpoint, self.collections_filter),
            (filters.is_item_endpoint, self.items_filter),
        ]
        for check, builder in endpoint_filters:
            if check(path):
                return builder

    async def proxy_request(self, request: Request, *, stream=False) -> httpx.Response:
        """Proxy a request to the upstream STAC API."""
        headers = MutableHeaders(request.headers)
        headers.setdefault("X-Forwarded-For", request.client.host)
        headers.setdefault("X-Forwarded-Host", request.url.hostname)

        path = request.url.path
        query = request.url.query
        # TODO: Should we only do this conditionally based on stream?
        body = (await request.body()).decode()

        # Apply filter if applicable
        filter_builder = self._get_filter(path)
        if filter_builder:
            cql_filter = await di.call_with_injected_dependencies(
                func=filter_builder,
                request=request,
            )
            if request.method == "GET":
                query = filters.insert_filter(qs=query, filter=cql_filter)
            elif request.method in ["POST", "PUT"]:
                if filters.is_search_endpoint(path):
                    try:
                        body = json.loads(body)
                    except json.JSONDecodeError:
                        ...
                    # TODO: Should append to body, not query
                    query = filters.insert_filter(qs=body, filter=cql_filter)
                else:
                    # TODO: Validate STAC items before create/update
                    ...

        # https://github.com/fastapi/fastapi/discussions/7382#discussioncomment-5136466
        rp_req = self.client.build_request(
            request.method,
            url=httpx.URL(
                path=path,
                query=query.encode("utf-8"),
            ),
            headers=headers,
            json=body,
        )
        logger.debug(f"Proxying request to {rp_req.url}")

        start_time = time.perf_counter()
        rp_resp = await self.client.send(rp_req, stream=stream)
        proxy_time = time.perf_counter() - start_time

        logger.debug(
            f"Received response status {rp_resp.status_code!r} from {rp_req.url} in {proxy_time:.3f}s"
        )
        rp_resp.headers["X-Upstream-Time"] = f"{proxy_time:.3f}"
        return rp_resp

    async def stream(self, request: Request) -> StreamingResponse:
        """Transparently proxy a request to the upstream STAC API."""
        rp_resp = await self.proxy_request(
            request,
            # collections_filter=collections_filter,
            stream=True,
        )
        return StreamingResponse(
            rp_resp.aiter_raw(),
            status_code=rp_resp.status_code,
            headers=rp_resp.headers,
            background=BackgroundTask(rp_resp.aclose),
        )
