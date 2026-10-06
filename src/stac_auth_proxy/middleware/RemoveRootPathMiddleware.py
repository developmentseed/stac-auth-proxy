"""Middleware to remove ROOT_PATH from incoming requests and update links in responses."""

import logging
from dataclasses import dataclass

from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..utils.requests import CHECKED_PATH, is_under_prefix, strip_prefix

logger = logging.getLogger(__name__)


# Where RemoveRootPathMiddleware records what it removed, for RestoreRootPathMiddleware
_ORIGINAL = "stac_auth_proxy.root_path"


@dataclass
class RemoveRootPathMiddleware:
    """
    Middleware to remove the root path of the request before the checks and the upstream
    see it.

    IMPORTANT: This middleware must be placed early in the middleware chain (ie late in
    the order of declaration) so that it trims the root_path from the request path before
    any middleware that may need to use the request path (e.g. EnforceAuthMiddleware).
    RestoreRootPathMiddleware puts it back before routing.
    """

    app: ASGIApp
    # ROOT_PATH. When unset, the app's own root path (scope["root_path"], e.g. from
    # FastAPI(root_path=...) or uvicorn --root-path) is removed instead, as
    # Starlette does when routing, so the checks see the path that is routed.
    root_path: str = ""

    def __post_init__(self) -> None:
        """Normalize the root path, as Settings does."""
        self.root_path = self.root_path.rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Remove ROOT_PATH from the request path if it exists."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope["path"]
        app_root_path = scope.get("root_path", "").rstrip("/")
        root_path = self.root_path or app_root_path
        # Only match the root path at a segment boundary ("/stac../x" is not under "/stac")
        under_root_path = bool(root_path) and is_under_prefix(path, root_path)

        # If root_path is set and path isn't under it, return 404
        if self.root_path and not under_root_path:
            response = Response("Not Found", status_code=404)
            logger.error(
                f"Root path {self.root_path!r} not found in path {scope['path']!r}"
            )
            await response(scope, receive, send)
            return

        if under_root_path:
            scope[_ORIGINAL] = (root_path, path, scope.get("raw_path"))
            scope["raw_path"] = path.encode()
            scope["path"] = strip_prefix(path, root_path)

        # "/stac/stac/x" is checked as "/stac/x". An upstream sharing the root path
        # (e.g. stac-fastapi reading the same ROOT_PATH variable) would remove it again
        # and act on "/x", so reject paths still under a root path.
        # Case-insensitively, as some upstreams (Express) route that way
        if any(
            prefix and is_under_prefix(scope["path"].lower(), prefix.lower())
            for prefix in (root_path, app_root_path)
        ):
            response = Response("Not Found", status_code=404)
            # A client error, so not logged at error level
            logger.info("Path %r still starts with a root path", scope["path"])
            await response(scope, receive, send)
            return

        scope[CHECKED_PATH] = scope["path"]
        return await self.app(scope, receive, send)


@dataclass
class RestoreRootPathMiddleware:
    """
    Put back the root path RemoveRootPathMiddleware removed, so routing (including
    Mounts) and URLs built from root_path (docs, url_for) see the usual ASGI scope.
    Request handlers then route on, and the proxy forwards, the path the checks saw.

    IMPORTANT: Must be the innermost middleware (first declared).
    """

    app: ASGIApp

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Restore the original path and root_path."""
        if scope["type"] != "http" or _ORIGINAL not in scope:
            return await self.app(scope, receive, send)

        root_path, path, raw_path = scope[_ORIGINAL]
        if path == root_path:
            # Starlette would route "/stac" under root_path "/stac" as "", which
            # matches nothing and redirects; the checks treated it as "/"
            path = f"{path}/"
            raw_path = raw_path + b"/" if raw_path is not None else None
        inner = {**scope, "root_path": root_path, "path": path}
        if raw_path is not None:
            inner["raw_path"] = raw_path

        def share_new_keys() -> None:
            # Keys set or changed while routing (route, endpoint, path_params,
            # state) are visible to outer middleware, as without this middleware
            scope.update(
                (key, value)
                for key, value in inner.items()
                if key not in ("root_path", "path", "raw_path")
            )

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                share_new_keys()
            await send(message)

        try:
            await self.app(inner, receive, send_wrapper)
        finally:
            share_new_keys()
