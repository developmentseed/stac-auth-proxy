"""Tooling to manage the reverse proxying of requests to an upstream STAC API."""

import logging
import time
from dataclasses import dataclass
from typing import Annotated, Callable, Optional

import httpx
from cql2 import Expr
from fastapi import Depends, Request
from starlette.background import BackgroundTask
from starlette.datastructures import MutableHeaders
from starlette.responses import StreamingResponse

from ..utils import filters

logger = logging.getLogger(__name__)


@dataclass
class ReverseProxyHandler:
    """Reverse proxy functionality."""

    upstream: str
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

        # Update annotations to support FastAPI's dependency injection
        for endpoint in [self.proxy_request, self.stream]:
            endpoint.__annotations__["collections_filter"] = Annotated[
                Optional[Expr],
                Depends(self.collections_filter or (lambda: None)),
            ]

    async def proxy_request(
        self,
        request: Request,
        *,
        collections_filter: Annotated[Optional[Expr], Depends(...)] = None,
        stream=False,
    ) -> httpx.Response:
        """Proxy a request to the upstream STAC API."""
        headers = MutableHeaders(request.headers)
        headers.setdefault("X-Forwarded-For", request.client.host)
        headers.setdefault("X-Forwarded-Host", request.url.hostname)

        path = request.url.path
        query = request.url.query

        # Apply filters
        if filters.is_collection_endpoint(path) and collections_filter:
            if request.method == "GET" and path == "/collections":
                query = filters.insert_filter(qs=query, filter=collections_filter)
        elif filters.is_item_endpoint(path) and self.items_filter:
            if request.method == "GET":
                query = filters.insert_filter(qs=query, filter=self.items_filter)

        # https://github.com/fastapi/fastapi/discussions/7382#discussioncomment-5136466
        rp_req = self.client.build_request(
            request.method,
            url=httpx.URL(
                path=path,
                query=query.encode("utf-8"),
            ),
            headers=headers,
            content=request.stream(),
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

    async def stream(
        self,
        request: Request,
        collections_filter: Annotated[Optional[Expr], Depends(...)],
    ) -> StreamingResponse:
        """Transparently proxy a request to the upstream STAC API."""
        rp_resp = await self.proxy_request(
            request,
            collections_filter=collections_filter,
            stream=True,
        )
        return StreamingResponse(
            rp_resp.aiter_raw(),
            status_code=rp_resp.status_code,
            headers=rp_resp.headers,
            background=BackgroundTask(rp_resp.aclose),
        )
