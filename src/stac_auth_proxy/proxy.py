import logging
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from fastapi import Request

from starlette.datastructures import MutableHeaders
from starlette.responses import StreamingResponse
from starlette.background import BackgroundTask

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ReverseProxy:
    upstream: str
    client: httpx.AsyncClient = None

    def __post_init__(self):
        self.client = self.client or httpx.AsyncClient(
            base_url=self.upstream,
            timeout=httpx.Timeout(timeout=15.0),
        )

    async def passthrough(self, request: Request):
        """Transparently proxy a request to the upstream STAC API."""

        headers = MutableHeaders(request.headers)

        # https://github.com/fastapi/fastapi/discussions/7382#discussioncomment-5136466
        rp_req = self.client.build_request(
            request.method,
            url=httpx.URL(
                path=request.url.path,
                query=request.url.query.encode("utf-8"),
            ),
            headers=headers,
            content=request.stream(),
        )
        logger.debug(f"Proxying request to {rp_req.url}")

        start_time = time.perf_counter()
        rp_resp = await self.client.send(rp_req, stream=True)
        proxy_time = time.perf_counter() - start_time

        logger.debug(
            f"Received response status {rp_resp.status_code!r} from {rp_req.url} in {proxy_time:.3f}s"
        )
        rp_resp.headers["X-Upstream-Time"] = f"{proxy_time:.3f}"

        return StreamingResponse(
            rp_resp.aiter_raw(),
            status_code=rp_resp.status_code,
            headers=rp_resp.headers,
            background=BackgroundTask(rp_resp.aclose),
        )
