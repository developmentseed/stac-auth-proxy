"""Utility functions for working with HTTP requests."""

import json
import re
from urllib.parse import urlparse

from starlette.requests import Request


def extract_variables(url: str) -> dict:
    """
    Extract variables from a URL path. Being that we use a catch-all endpoint for the proxy,
    we can't rely on the path parameters that FastAPI provides.
    """
    path = urlparse(url).path
    # This allows either /items or /bulk_items, with an optional item_id following.
    pattern = r"^/collections/(?P<collection_id>[^/]+)(?:/(?:items|bulk_items)(?:/(?P<item_id>[^/]+))?)?/?$"
    match = re.match(pattern, path)
    return {k: v for k, v in match.groupdict().items() if v} if match else {}


def dict_to_bytes(d: dict) -> bytes:
    """Convert a dictionary to a body."""
    return json.dumps(d, separators=(",", ":")).encode("utf-8")


def matches_route(request: Request, url_patterns: dict[str, list[str]]) -> bool:
    """
    Test if the incoming request.path and request.method match any of the patterns
    (and their methods) in url_patterns.
    """
    path = request.url.path  # e.g. '/collections/123'
    method = request.method.casefold()  # e.g. 'post'

    for pattern, allowed_methods in url_patterns.items():
        if re.match(pattern, path) and method in [
            m.casefold() for m in allowed_methods
        ]:
            return True

    return False
