"""Utility functions for working with HTTP requests."""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence
from urllib.parse import urlparse

from starlette.requests import Request

from ..config import EndpointMethods

logger = logging.getLogger(__name__)


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


def _check_endpoint_match(
    path: str,
    method: str,
    endpoints: EndpointMethods,
) -> tuple[bool, Sequence[str]]:
    """Check if the path and method match any endpoint in the given endpoints map."""
    for pattern, endpoint_methods in endpoints.items():
        if re.match(pattern, path):
            for endpoint_method in endpoint_methods:
                required_scopes: Sequence[str] = []
                if isinstance(endpoint_method, tuple):
                    endpoint_method, _required_scopes = endpoint_method
                    if _required_scopes:  # Ignore empty scopes, e.g. `["POST", ""]`
                        required_scopes = _required_scopes.split(" ")
                if method.casefold() == endpoint_method.casefold():
                    return True, required_scopes
    return False, []


def find_match(
    path: str,
    method: str,
    private_endpoints: EndpointMethods,
    public_endpoints: EndpointMethods,
    default_public: bool,
) -> "MatchResult":
    """Check if the given path and method match any of the regex patterns and methods in the endpoints."""
    primary_endpoints = private_endpoints if default_public else public_endpoints
    matched, required_scopes = _check_endpoint_match(path, method, primary_endpoints)
    if matched:
        return MatchResult(
            is_private=default_public,
            required_scopes=required_scopes,
        )

    # If default_public and no match found in private_endpoints, it's public
    if default_public:
        return MatchResult(is_private=False)

    # If not default_public, check private_endpoints for required scopes
    matched, required_scopes = _check_endpoint_match(path, method, private_endpoints)
    if matched:
        return MatchResult(is_private=True, required_scopes=required_scopes)

    # Default case: if not default_public and no explicit match, it's private
    return MatchResult(is_private=True)


@dataclass
class MatchResult:
    """Result of a match between a path and method and a set of endpoints."""

    is_private: bool
    required_scopes: Sequence[str] = field(default_factory=list)


def build_server_timing_header(
    current_value: Optional[str] = None, *, name: str, desc: str, dur: float
):
    """Append a timing header to headers."""
    metric = f'{name};desc="{desc}";dur={dur:.3f}'
    if current_value:
        return f"{current_value}, {metric}"
    return metric


def parse_forwarded_header(forwarded_header: str) -> Dict[str, str]:
    """
    Parse the Forwarded header according to RFC 7239.

    Args:
        forwarded_header: The Forwarded header value

    Returns:
        Dictionary containing parsed forwarded information (proto, host, for, by, etc.)

    Example:
        >>> parse_forwarded_header("for=192.0.2.43; by=203.0.113.60; proto=https; host=api.example.com")
        {'for': '192.0.2.43', 'by': '203.0.113.60', 'proto': 'https', 'host': 'api.example.com'}

    """
    # Forwarded header format: "for=192.0.2.43, for=198.51.100.17; by=203.0.113.60; proto=https; host=example.com"
    # The format is: for=value1, for=value2; by=value; proto=value; host=value
    # We need to parse all the key=value pairs, taking the first 'for' value
    forwarded_info = {}

    try:
        # Parse all key=value pairs separated by semicolons
        for pair in forwarded_header.split(";"):
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"')

                # For 'for' field, only take the first value if there are multiple
                if key == "for" and key not in forwarded_info:
                    # Extract the first for value (before comma if present)
                    first_for_value = value.split(",")[0].strip()
                    forwarded_info[key] = first_for_value
                elif key != "for":
                    # For other fields, just use the value as-is
                    forwarded_info[key] = value
    except Exception as e:
        logger.warning(f"Failed to parse Forwarded header '{forwarded_header}': {e}")
        return {}

    return forwarded_info


def get_base_url(request: Request) -> str:
    """
    Get the request's base URL, accounting for forwarded headers from load balancers/proxies.

    This function handles both the standard Forwarded header (RFC 7239) and legacy
    X-Forwarded-* headers to reconstruct the original client URL when the service
    is deployed behind load balancers or reverse proxies.

    Args:
        request: The Starlette request object

    Returns:
        The reconstructed client base URL

    Example:
        >>> # With Forwarded header
        >>> request.headers = {"Forwarded": "for=192.0.2.43; proto=https; host=api.example.com"}
        >>> get_base_url(request)
        "https://api.example.com/"

        >>> # With X-Forwarded-* headers
        >>> request.headers = {"X-Forwarded-Host": "api.example.com", "X-Forwarded-Proto": "https"}
        >>> get_base_url(request)
        "https://api.example.com/"

    """
    # Check for standard Forwarded header first (RFC 7239)
    forwarded_header = request.headers.get("Forwarded")
    if forwarded_header:
        try:
            forwarded_info = parse_forwarded_header(forwarded_header)
            # Only use Forwarded header if we successfully parsed it and got useful info
            if forwarded_info and (
                "proto" in forwarded_info or "host" in forwarded_info
            ):
                scheme = forwarded_info.get("proto", request.url.scheme)
                host = forwarded_info.get("host", request.url.netloc)
                # Note: Forwarded header doesn't include path, so we use request.base_url.path
                path = request.base_url.path
                return f"{scheme}://{host}{path}"
        except Exception as e:
            logger.warning(f"Failed to parse Forwarded header: {e}")

    # Fall back to legacy X-Forwarded-* headers
    forwarded_host = request.headers.get("X-Forwarded-Host")
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    forwarded_path = request.headers.get("X-Forwarded-Path")

    if forwarded_host:
        # Use forwarded headers to reconstruct the original client URL
        scheme = forwarded_proto or request.url.scheme
        netloc = forwarded_host
        # Use forwarded path if available, otherwise use request base URL path
        path = forwarded_path or request.base_url.path
    else:
        # Fall back to the request's base URL if no forwarded headers
        scheme = request.url.scheme
        netloc = request.url.netloc
        path = request.base_url.path

    return f"{scheme}://{netloc}{path}"
