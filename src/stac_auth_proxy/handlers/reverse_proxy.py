"""Tooling to manage the reverse proxying of requests to an upstream STAC API."""

import logging
import time

import httpx
from fastapi import Request
from starlette.datastructures import MutableHeaders
from starlette.responses import Response

logger = logging.getLogger(__name__)


async def proxy_request(request: Request) -> Response:
    """Proxy a request to the upstream STAC API."""
    headers = MutableHeaders(request.headers)
    headers.setdefault("X-Forwarded-For", request.client.host)
    headers.setdefault("X-Forwarded-Host", request.url.hostname)

    try:
        client = request.app.state.client
    except AttributeError as e:
        raise SystemError(
            "Client not found in request.app.state. "
            "Set an httpx client in the app state."
        ) from e

    # https://github.com/fastapi/fastapi/discussions/7382#discussioncomment-5136466
    rp_req = client.build_request(
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
    rp_resp = await client.send(rp_req, stream=True)
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
