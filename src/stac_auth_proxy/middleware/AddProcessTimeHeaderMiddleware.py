"""Middleware to add Server-Timing header with proxy processing time."""

import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from stac_auth_proxy.utils.requests import build_server_timing_header


class AddProcessTimeHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware to add Server-Timing header with proxy processing time."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Add Server-Timing header with proxy processing time to the response."""
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time

        # Add Server-Timing header with proxy processing time
        response.headers["Server-Timing"] = build_server_timing_header(
            response.headers.get("Server-Timing"),
            name="proxy",
            dur=process_time,
            desc="Proxy processing time",
        )

        return response
