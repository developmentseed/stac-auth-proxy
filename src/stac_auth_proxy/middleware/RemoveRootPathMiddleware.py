"""Middleware to remove BASE_PATH from incoming requests and update links in responses."""

import logging
from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


@dataclass
class RemoveRootPathMiddleware:
    """
    Middleware to remove the base path of the request before it is sent to the upstream
    server.

    IMPORTANT: This middleware must be placed early in the middleware chain (ie late in
    the order of declaration) so that it trims the base_path from the request path before
    any middleware that may need to use the request path (e.g. EnforceAuthMiddleware).
    """

    app: ASGIApp
    base_path: str
    transform_links: bool = True

    json_content_type_expr: str = r"application/(geo\+)?json"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Remove BASE_PATH from the request path if it exists."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope["path"]

        # Remove base_path if it exists at the start of the path
        if path.startswith(self.base_path):
            scope["raw_path"] = scope["path"].encode()
            scope["path"] = path[len(self.base_path) :] or "/"

        return await self.app(scope, receive, send)
