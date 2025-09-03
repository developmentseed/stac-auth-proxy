"""Middleware to add Server-Timing header with proxy processing time."""

import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class AddProcessTimeHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware to add Server-Timing header with proxy processing time."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Add Server-Timing header with proxy processing time to the response."""
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time

        # Add Server-Timing header with proxy processing time
        # Format: Server-Timing: proxy;dur=123.456
        server_timing_value = f"proxy;dur={process_time:.3f}"

        # If there's already a Server-Timing header, append to it
        existing_timing = response.headers.get("Server-Timing")
        if existing_timing:
            response.headers["Server-Timing"] = (
                f"{existing_timing}, {server_timing_value}"
            )
        else:
            response.headers["Server-Timing"] = server_timing_value

        return response
