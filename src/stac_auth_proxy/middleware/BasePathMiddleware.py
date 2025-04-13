"""Middleware to remove BASE_PATH from incoming requests and update links in responses."""

import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from ..utils.middleware import JsonResponseMiddleware
from ..utils.stac import get_links

logger = logging.getLogger(__name__)


@dataclass
class BasePathMiddleware(JsonResponseMiddleware):
    """
    Middleware to handle the base path of the request and update links in responses.

    IMPORTANT: This middleware must be the first middleware in the chain (ie last in the
    order of declaration) so that it trims the base_path from the request path before
    other middleware review the request.
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

        return await super().__call__(scope, receive, send)

    def should_transform_response(self, request: Request, scope: Scope) -> bool:
        """Only transform responses with JSON content type."""
        return bool(
            re.match(
                self.json_content_type_expr,
                Headers(scope=scope).get("content-type", ""),
            )
        )

    def transform_json(self, data: dict[str, Any], request: Request) -> dict[str, Any]:
        """Update links in the response to include base_path."""
        for link in get_links(data):
            href = link.get("href")
            if not href:
                continue

            try:
                parsed_link = urlparse(href)

                # Ignore links that are not for this proxy
                if parsed_link.netloc != request.headers.get("host"):
                    continue

                parsed_link = parsed_link._replace(
                    path=f"{self.base_path}{parsed_link.path}"
                )
                link["href"] = urlunparse(parsed_link)
            except Exception as e:
                logger.warning("Failed to parse link href %s: %s", href, str(e))

        return data
