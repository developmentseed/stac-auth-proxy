"""Middleware to reject requests whose checked and routed paths may differ."""

from dataclasses import dataclass

from starlette.datastructures import URL
from starlette.types import ASGIApp, Receive, Scope, Send

from ..utils.middleware import bad_request


@dataclass(frozen=True)
class RejectAmbiguousPathMiddleware:
    """
    Reject requests whose ``request.url.path`` differs from the routed path.

    Auth, filter and transaction checks match on ``request.url.path``, which
    Starlette rebuilds from the scope's scheme, server and path. Any request where
    its path differs from ``scope["path"]`` (e.g. "/search%23" truncated to
    "/search", or a scheme copied from a client's X-Forwarded-Proto) is rejected.

    Paths that are only ambiguous once forwarded upstream are rejected by
    ``ReverseProxyHandler``, so the app's own routes (non-proxy mode) accept them.

    IMPORTANT: Must run before any middleware that uses the request path.
    """

    app: ASGIApp

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Reject ambiguous request paths."""
        if scope["type"] == "http":
            error = None
            if not self.url_matches_scope(scope):
                error = "Invalid request path."
            elif not self.query_is_utf8(scope):
                # Starlette's request.url (used by every check) can't decode it
                error = "Invalid query string."
            if error:
                return await bad_request(error)(scope, receive, send)
        return await self.app(scope, receive, send)

    @staticmethod
    def query_is_utf8(scope: Scope) -> bool:
        """Whether the raw query string is valid UTF-8."""
        try:
            scope.get("query_string", b"").decode()
        except UnicodeDecodeError:
            return False
        return True

    @staticmethod
    def url_matches_scope(scope: Scope) -> bool:
        """Whether Starlette's request URL has the scope's path."""
        try:
            # Without the query string, which isn't compared (and may not be UTF-8)
            url = URL(scope={**scope, "query_string": b""})
        except (KeyError, ValueError, TypeError):  # e.g. unknown scheme
            return False
        # Only the path is used by the checks. The query string is forwarded and
        # parsed from scope["query_string"], never request.url.query (which a raw "#"
        # truncates), and the scheme and host may legitimately be missing (e.g. a
        # unix socket with no valid Host header).
        return url.path == scope["path"]
