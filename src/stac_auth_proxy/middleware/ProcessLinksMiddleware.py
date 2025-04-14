"""Middleware to remove the application root path from incoming requests and update links in responses."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Scope

from ..utils.middleware import JsonResponseMiddleware
from ..utils.stac import get_links

logger = logging.getLogger(__name__)


@dataclass
class ProcessLinksMiddleware(JsonResponseMiddleware):
    """
    Middleware to update links in responses, removing the upstream_url path and adding
    the root_path if it exists.
    """

    app: ASGIApp
    upstream_url: str
    root_path: Optional[str] = None

    json_content_type_expr: str = r"application/(geo\+)?json"

    def should_transform_response(self, request: Request, scope: Scope) -> bool:
        """Only transform responses with JSON content type."""
        return bool(
            re.match(
                self.json_content_type_expr,
                Headers(scope=scope).get("content-type", ""),
            )
        )

    def transform_json(self, data: dict[str, Any], request: Request) -> dict[str, Any]:
        """Update links in the response to include root_path."""
        for link in get_links(data):
            href = link.get("href")
            if not href:
                continue

            try:
                parsed_link = urlparse(href)

                # Ignore links that are not for this proxy
                if parsed_link.netloc != request.headers.get("host"):
                    continue

                # Remove the upstream_url path from the link if it exists
                if urlparse(self.upstream_url).path != "/":
                    parsed_link = parsed_link._replace(
                        path=parsed_link.path[len(urlparse(self.upstream_url).path) :]
                    )

                # Add the root_path to the link if it exists
                if self.root_path:
                    parsed_link = parsed_link._replace(
                        path=f"{self.root_path}{parsed_link.path}"
                    )

                link["href"] = urlunparse(parsed_link)
            except Exception as e:
                logger.error(
                    "Failed to parse link href %r, (ignoring): %s", href, str(e)
                )

        return data
