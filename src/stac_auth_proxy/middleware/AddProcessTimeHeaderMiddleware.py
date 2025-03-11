"""Middleware to add a header with the process time to the response."""

import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class AddProcessTimeHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware to add a header with the process time to the response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Add a header with the process time to the response."""
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.3f}"
        return response
