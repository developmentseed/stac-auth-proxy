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
from ..utils.requests import get_base_url
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
        # Get the client's actual base URL (accounting for load balancers/proxies)
        req_base_url = get_base_url(request)
        parsed_req_url = urlparse(req_base_url)
        parsed_upstream_url = urlparse(self.upstream_url)

        for link in get_links(data):
            href = link.get("href")
            if not href:
                continue

            try:
                parsed_link = urlparse(href)

                if parsed_link.netloc not in [
                    parsed_req_url.netloc,
                    parsed_upstream_url.netloc,
                ]:
                    logger.debug(
                        "Ignoring link %s because it is not for an endpoint behind this proxy (%s or %s)",
                        href,
                        parsed_req_url.netloc,
                        parsed_upstream_url.netloc,
                    )
                    continue

                # If the link path is not a descendant of the upstream path, don't transform it
                if parsed_upstream_url.path != "/" and not parsed_link.path.startswith(
                    parsed_upstream_url.path
                ):
                    logger.debug(
                        "Ignoring link %s because it is not descendant of upstream path (%s)",
                        href,
                        parsed_upstream_url.path,
                    )
                    continue

                # Replace the upstream host with the client's host
                if parsed_link.netloc == parsed_upstream_url.netloc:
                    parsed_link = parsed_link._replace(
                        netloc=parsed_req_url.netloc
                    )._replace(scheme=parsed_req_url.scheme)

                # Rewrite the link path
                if parsed_upstream_url.path != "/" and parsed_link.path.startswith(
                    parsed_upstream_url.path
                ):
                    parsed_link = parsed_link._replace(
                        path=parsed_link.path[len(parsed_upstream_url.path) :]
                    )

                # Add the root_path to the link if it exists
                if self.root_path:
                    parsed_link = parsed_link._replace(
                        path=f"{self.root_path}{parsed_link.path}"
                    )

                logger.debug(
                    "Rewriting %r link %r to %r",
                    link.get("rel"),
                    href,
                    urlunparse(parsed_link),
                )
                link["href"] = urlunparse(parsed_link)

            except Exception as e:
                logger.error(
                    "Failed to parse link href %r, (ignoring): %s", href, str(e)
                )

        return data
