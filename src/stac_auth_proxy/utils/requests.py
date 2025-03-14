"""Utility functions for working with HTTP requests."""

import json
import re
from dataclasses import dataclass, field
from typing import Sequence
from urllib.parse import urlparse

from ..config import EndpointMethods


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


def find_match(
    path: str,
    method: str,
    private_endpoints: EndpointMethods,
    public_endpoints: EndpointMethods,
    default_public: bool,
) -> "MatchResult":
    """Check if the given path and method match any of the regex patterns and methods in the endpoints."""
    endpoints = private_endpoints if default_public else public_endpoints
    for pattern, endpoint_methods in endpoints.items():
        if not re.match(pattern, path):
            continue
        for endpoint_method in endpoint_methods:
            required_scopes: Sequence[str] = []
            if isinstance(endpoint_method, tuple):
                endpoint_method, required_scopes = endpoint_method
            if method.casefold() == endpoint_method.casefold():
                # If default_public, we're looking for a private endpoint.
                # If not default_public, we're looking for a public endpoint.
                return MatchResult(
                    is_private=default_public,
                    required_scopes=required_scopes,
                )
    return MatchResult(is_private=not default_public)


@dataclass
class MatchResult:
    """Result of a match between a path and method and a set of endpoints."""

    is_private: bool
    required_scopes: Sequence[str] = field(default_factory=list)
