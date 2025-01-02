import re

from urllib.parse import urlparse
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
