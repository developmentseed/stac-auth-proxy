# TODO
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class EnforceAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce authentication."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Enforce authentication."""
        return await call_next(request)
