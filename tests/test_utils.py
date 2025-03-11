"""Tests for OpenAPI spec handling."""

import pytest
from utils import parse_query_string

from stac_auth_proxy.utils.requests import extract_variables


@pytest.mark.parametrize(
    "url, expected",
    (
        ("/collections/123", {"collection_id": "123"}),
        ("/collections/123/items", {"collection_id": "123"}),
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
