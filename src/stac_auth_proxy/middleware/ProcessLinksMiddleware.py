"""Middleware to remove the application root path from incoming requests and update links in responses."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import ParseResult, urlparse, urlunparse

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Scope

from ..utils.middleware import JsonResponseMiddleware
from ..utils.requests import get_base_url
from ..utils.stac import get_links

logger = logging.getLogger(__name__)


def _extract_hostname(netloc: str) -> str:
    """
    Extract hostname from netloc, ignoring port number.

    Args:
        netloc: Network location string (e.g., "localhost:8080" or "example.com")

    Returns:
        Hostname without port (e.g., "localhost" or "example.com")

    """
    if ":" in netloc:
        if netloc.startswith("["):
            # IPv6 with port: [::1]:8080
            end_bracket = netloc.rfind("]")
            if end_bracket != -1:
                return netloc[: end_bracket + 1]
        # Regular hostname with port: localhost:8080
        return netloc.split(":", 1)[0]
    return netloc


def _hostnames_match(hostname1: str, hostname2: str) -> bool:
    """
    Check if two hostnames match, ignoring case and port.

    Args:
        hostname1: First hostname (may include port)
        hostname2: Second hostname (may include port)

    Returns:
        True if hostnames match (case-insensitive, ignoring port)

    """
    return _extract_hostname(hostname1).lower() == _extract_hostname(hostname2).lower()


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
            try:
                self._update_link(link, parsed_req_url, parsed_upstream_url)
            except Exception as e:
                logger.error(
                    "Failed to parse link href %r, (ignoring): %s",
                    link.get("href"),
                    str(e),
                )
        return data

    def _update_link(
        self, link: dict[str, Any], request_url: ParseResult, upstream_url: ParseResult
    ) -> None:
        """
        Ensure that link hrefs that are local to upstream url are rewritten as local to
        the proxy.
        """
        if "href" not in link:
            logger.warning("Link %r has no href", link)
            return

        parsed_link = urlparse(link["href"])

        link_hostname = _extract_hostname(parsed_link.netloc)
        request_hostname = _extract_hostname(request_url.netloc)
        upstream_hostname = _extract_hostname(upstream_url.netloc)

        if not (
            _hostnames_match(link_hostname, request_hostname)
            or _hostnames_match(link_hostname, upstream_hostname)
        ):
            logger.debug(
                "Ignoring link %s because it is not for an endpoint behind this proxy (%s or %s)",
                link["href"],
                request_url.netloc,
                upstream_url.netloc,
            )
            return

        # If the link path is not a descendant of the upstream path, don't transform it
        if upstream_url.path != "/" and not parsed_link.path.startswith(
            upstream_url.path
        ):
            logger.debug(
                "Ignoring link %s because it is not descendant of upstream path (%s)",
                link["href"],
                upstream_url.path,
            )
            return

        # Replace the upstream host with the client's host
        link_matches_upstream = _hostnames_match(
            parsed_link.netloc, upstream_url.netloc
        )
        parsed_link = parsed_link._replace(netloc=request_url.netloc)
        if link_matches_upstream:
            # Link hostname matches upstream: also replace scheme with request URL's scheme
            parsed_link = parsed_link._replace(scheme=request_url.scheme)
        # If link matches request hostname, scheme is preserved (handles https://localhost:443 -> http://localhost)

        # Remove the upstream prefix from the link path
        if upstream_url.path != "/" and parsed_link.path.startswith(upstream_url.path):
            parsed_link = parsed_link._replace(
                path=parsed_link.path[len(upstream_url.path) :]
            )

        # Add the root_path to the link if it exists
        if self.root_path:
            parsed_link = parsed_link._replace(
                path=f"{self.root_path}{parsed_link.path}"
            )

        updated_href = urlunparse(parsed_link)
        if updated_href == link["href"]:
            return

        logger.debug(
            "Rewriting %r link %r to %r",
            link.get("rel"),
            link["href"],
            updated_href,
        )

        link["href"] = updated_href
