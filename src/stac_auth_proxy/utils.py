"""Utility functions."""

import re
from urllib.parse import urlparse

from fastapi.dependencies.models import Dependant
from httpx import Headers


def safe_headers(headers: Headers) -> dict[str, str]:
    """Scrub headers that should not be proxied to the client."""
    excluded_headers = [
        "content-length",
        "content-encoding",
    ]
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in excluded_headers
    }


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


def has_any_security_requirements(dependency: Dependant) -> bool:
    """
    Recursively check if any dependency within the hierarchy has a non-empty
    security_requirements list.
    """
    if dependency.security_requirements:
        return True
    return any(
        has_any_security_requirements(sub_dep) for sub_dep in dependency.dependencies
    )
