"""Tooling to manage the reverse proxying of requests to an upstream STAC API."""

import logging
import time
from dataclasses import dataclass, field

import httpx
from fastapi import Request
from starlette.datastructures import MutableHeaders
from starlette.responses import Response

logger = logging.getLogger(__name__)


@dataclass
class ReverseProxyHandler:
    """Reverse proxy functionality."""

    upstream: str
    client: httpx.AsyncClient = None
    timeout: httpx.Timeout = field(default_factory=lambda: httpx.Timeout(timeout=15.0))

    proxy_name: str = "stac-auth-proxy"
    override_host: bool = True

    def __post_init__(self):
        """Initialize the HTTP client."""
        self.client = self.client or httpx.AsyncClient(
            base_url=self.upstream,
            timeout=self.timeout,
            http2=True,
        )

    def _prepare_headers(self, request: Request) -> MutableHeaders:
        """Prepare headers for the proxied request."""
        headers = MutableHeaders(request.headers)

        # Handle null client host
        client_host = request.client.host if request.client else "unknown"
        proto = request.url.scheme

        host = request.url.hostname
        if request.url.port not in [80, 443]:
            host = f"{host}:{request.url.port}"

        headers.setdefault("X-Forwarded-For", client_host)
        headers.setdefault("X-Forwarded-Host", request.url.hostname)
        headers.setdefault("X-Forwarded-Proto", proto)
        headers.setdefault(
            "Forwarded",
            f"for={client_host};host={host};proto={proto}",
        )
        headers.setdefault("Via", f"1.1 {self.proxy_name}")

        if self.override_host:
            headers["Host"] = self.client.base_url.netloc.decode("utf-8")
            if self.client.base_url.port not in [80, 443]:
                headers["Host"] = f'{headers["Host"]}:{request.url.port}'

        return headers

    async def proxy_request(self, request: Request) -> Response:
        """Proxy a request to the upstream STAC API."""
        headers = self._prepare_headers(request)

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

        # NOTE: HTTPX adds headers, so we need to trim them before sending request
        for h in rp_req.headers:
            if h not in headers:
                del rp_req.headers[h]

        logger.debug(f"Proxying request to {rp_req.url}")

        start_time = time.perf_counter()
        rp_resp = await self.client.send(rp_req, stream=True)
        proxy_time = time.perf_counter() - start_time

        logger.debug(
            f"Received response status {rp_resp.status_code!r} from {rp_req.url} in {proxy_time:.3f}s"
        )
        rp_resp.headers["X-Upstream-Time"] = f"{proxy_time:.3f}"

        # We read the content here to make use of HTTPX's decompression, ensuring we have
        # non-compressed content for the middleware to work with.
        content = await rp_resp.aread()
        if rp_resp.headers.get("Content-Encoding"):
            del rp_resp.headers["Content-Encoding"]

        return Response(
            content=content,
            status_code=rp_resp.status_code,
            headers=dict(rp_resp.headers),
        )
