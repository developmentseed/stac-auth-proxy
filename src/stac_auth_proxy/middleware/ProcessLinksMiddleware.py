"""Middleware to remove the application root path from incoming requests and update links in responses."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional, Sequence
from urllib.parse import ParseResult, urlparse, urlunparse

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
    root_path_skip_prefixes: Sequence[str] = ()

    json_content_type_expr: str = r"application/(geo\+)?json"

    def __post_init__(self) -> None:
        """Normalize skip prefixes, dropping empty entries and trailing slashes."""
        self.root_path_skip_prefixes = tuple(
            prefix.rstrip("/")
            for prefix in self.root_path_skip_prefixes
            if prefix.rstrip("/")
        )

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

        # Leave links to sibling services untouched. On a shared-host deployment
        # (e.g. this proxy at /stac and a tiler at /raster on the same hostname),
        # same-host links to other services must not be treated as local to the
        # upstream API and must not have the root_path prepended.
        if parsed_link.netloc == request_url.netloc and any(
            parsed_link.path == prefix or parsed_link.path.startswith(f"{prefix}/")
            for prefix in self.root_path_skip_prefixes
        ):
            logger.debug(
                "Ignoring link %s because its path matches a configured skip prefix (%s)",
                link["href"],
                self.root_path_skip_prefixes,
            )
            return

        if parsed_link.netloc not in [
            request_url.netloc,
            upstream_url.netloc,
        ]:
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
        if parsed_link.netloc == upstream_url.netloc:
            parsed_link = parsed_link._replace(netloc=request_url.netloc)._replace(
                scheme=request_url.scheme
            )

        # Remove the upstream prefix from the link path
        if upstream_url.path != "/" and parsed_link.path.startswith(upstream_url.path):
            parsed_link = parsed_link._replace(
                path=parsed_link.path[len(upstream_url.path) :]
            )

        # Add the root_path to the link if it exists
        if self.root_path and not (
            parsed_link.path.startswith(f"{self.root_path}/")
            or parsed_link.path == self.root_path
        ):
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
