"""Middleware to remove ROOT_PATH from incoming requests and update links in responses."""

import logging
from dataclasses import dataclass

from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


@dataclass
class RemoveRootPathMiddleware:
    """
    Middleware to remove the root path of the request before it is sent to the upstream
    server.

    IMPORTANT: This middleware must be placed early in the middleware chain (ie late in
    the order of declaration) so that it trims the root_path from the request path before
    any middleware that may need to use the request path (e.g. EnforceAuthMiddleware).
    """

    app: ASGIApp
    root_path: str

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Remove ROOT_PATH from the request path if it exists."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # If root_path is set and path doesn't start with it, return 404
        if self.root_path and not scope["path"].startswith(self.root_path):
            response = Response("Not Found", status_code=404)
            logger.error(
                f"Root path {self.root_path!r} not found in path {scope['path']!r}"
            )
            await response(scope, receive, send)
            return

        # Remove root_path if it exists at the start of the path
        if scope["path"].startswith(self.root_path):
            scope["raw_path"] = scope["path"].encode()
            scope["path"] = scope["path"][len(self.root_path) :] or "/"

        return await self.app(scope, receive, send)
