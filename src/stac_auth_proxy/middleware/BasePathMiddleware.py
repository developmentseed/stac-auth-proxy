"""Middleware to remove BASE_PATH from incoming requests."""

from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass
class RemoveRootPathMiddleware:
    """
    Middleware to remove BASE_PATH from incoming requests.

    IMPORTANT: This middleware must be the first middleware in the chain (ie last in the
    order of declaration) so that it trims the base_path from the request path before
    other middleware review the request.
    """

    app: ASGIApp
    base_path: str

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
