"""Tooling to manage the reverse proxying of requests to an upstream STAC API."""

import logging
import time
from dataclasses import dataclass
from typing import Optional, Annotated

from cql2 import Expr
import httpx
from fastapi import Request, Depends
from starlette.background import BackgroundTask
from starlette.datastructures import MutableHeaders
from starlette.responses import StreamingResponse

from ..utils import update_qs

logger = logging.getLogger(__name__)


@dataclass
class ReverseProxyHandler:
    """Reverse proxy functionality."""

    upstream: str
    client: httpx.AsyncClient = None
    collections_filter: Optional[callable] = None
    items_filter: Optional[callable] = None

    def __post_init__(self):
        """Initialize the HTTP client."""
        self.client = self.client or httpx.AsyncClient(
            base_url=self.upstream,
            timeout=httpx.Timeout(timeout=15.0),
        )

        self.proxy_request.__annotations__["collections_filter"] = Annotated[
            Optional[Expr], Depends(self.collections_filter.dependency)
        ]
        self.stream.__annotations__["collections_filter"] = Annotated[
            Optional[Expr], Depends(self.collections_filter.dependency)
        ]

    async def proxy_request(
        self,
        request: Request,
        *,
        collections_filter: Annotated[Optional[Expr], Depends(...)],
        stream=False,
    ) -> httpx.Response:
        """Proxy a request to the upstream STAC API."""
        headers = MutableHeaders(request.headers)
        headers.setdefault("X-Forwarded-For", request.client.host)
        headers.setdefault("X-Forwarded-Host", request.url.hostname)

        path = request.url.path
        query = request.url.query.encode("utf-8")

        # https://github.com/fastapi/fastapi/discussions/7382#discussioncomment-5136466
        # TODO: Examine filters
        if collections_filter:
            if request.method == "GET" and path == "/collections":
                query += b"&" + update_qs(
                    request.query_params, filter=collections_filter.to_text()
                )

        url = httpx.URL(
            path=path,
            query=query,
        )

        rp_req = self.client.build_request(
            request.method,
            url=url,
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
