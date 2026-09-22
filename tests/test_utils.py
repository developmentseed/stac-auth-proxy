"""Tests for OpenAPI spec handling."""

import pytest
from utils import parse_query_string

from stac_auth_proxy.utils.requests import (
    extract_variables,
    find_match,
    get_base_url,
    parse_forwarded_header,
)


@pytest.mark.parametrize(
    "url, expected",
    (
        ("/collections/123", {"collection_id": "123"}),
        ("/collections/123/items", {"collection_id": "123"}),
        ("/collections/123/queryables", {"collection_id": "123"}),
        ("/collections/123/bulk_items", {"collection_id": "123"}),
        ("/collections/123/items/456", {"collection_id": "123", "item_id": "456"}),
        ("/collections/123/bulk_items/456", {"collection_id": "123", "item_id": "456"}),
        ("/other/123", {}),
    ),
)
def test_extract_variables(url, expected):
    """Test extracting variables from a URL path."""
    assert extract_variables(url) == expected


@pytest.mark.parametrize(
    "query, expected",
    (
        ("foo=bar", {"foo": "bar"}),
        (
            'filter={"xyz":"abc"}&filter-lang=cql2-json',
            {"filter": {"xyz": "abc"}, "filter-lang": "cql2-json"},
        ),
    ),
)
def test_parse_query_string(query, expected):
    """Validate test helper for parsing query strings."""
    assert parse_query_string(query) == expected


@pytest.mark.parametrize(
    "header, expected",
    (
        # Basic Forwarded header parsing
        (
            "for=192.0.2.43; by=203.0.113.60; proto=https; host=api.example.com",
            {
                "for": "192.0.2.43",
                "by": "203.0.113.60",
                "proto": "https",
                "host": "api.example.com",
            },
        ),
        # Multiple for values - should only take the first
        (
            "for=192.0.2.43, for=198.51.100.17; by=203.0.113.60; proto=https; host=api.example.com",
            {
                "for": "192.0.2.43",
                "by": "203.0.113.60",
                "proto": "https",
                "host": "api.example.com",
            },
        ),
        # Quoted values
        (
            'for="192.0.2.43"; by="203.0.113.60"; proto="https"; host="api.example.com"',
            {
                "for": "192.0.2.43",
                "by": "203.0.113.60",
                "proto": "https",
                "host": "api.example.com",
            },
        ),
        # Malformed content
        ("malformed header content", {}),
        # Empty content
        ("", {}),
    ),
)
def test_parse_forwarded_header(header, expected):
    """Test Forwarded header parsing with various scenarios."""
    result = parse_forwarded_header(header)
    assert result == expected


@pytest.mark.parametrize(
    "headers, expected_url",
    (
        # Forwarded header
        (
            [
                (b"host", b"internal-proxy:8080"),
                (b"forwarded", b"for=192.0.2.43; proto=https; host=api.example.com"),
            ],
            "https://api.example.com/",
        ),
        # X-Forwarded-* headers
        (
            [
                (b"host", b"internal-proxy:8080"),
                (b"x-forwarded-host", b"api.example.com"),
                (b"x-forwarded-proto", b"https"),
            ],
            "https://api.example.com/",
        ),
        # No forwarded headers
        (
            [
                (b"host", b"proxy.example.com"),
            ],
            "http://proxy.example.com/",
        ),
    ),
)
def test_get_base_url(headers, expected_url):
    """Test get_base_url with various header configurations."""
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": headers,
    }
    request = Request(scope)

    result = get_base_url(request)
    assert result == expected_url


@pytest.mark.parametrize(
    "collections_filter_path",
    [
        r"^/collections/(?P<collection_id>[^/]+)/aggregations$",
        [
            r"^/collections/(?P<collection_id>[^/]+)/aggregate$",
            r"^/collections/(?P<collection_id>[^/]+)/aggregations$",
        ],
    ],
    ids=["bare string", "sequence"],
)
def test_find_match_authenticates_filter_paths(collections_filter_path):
    """Any path carrying a filter requires auth, whatever default_public says."""
    match = find_match(
        "/collections/123/aggregations",
        "GET",
        private_endpoints={},
        public_endpoints={},
        default_public=True,
        collections_filter_path=collections_filter_path,
    )
    assert match.uses_auth is True
