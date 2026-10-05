"""Tests for OpenAPI spec handling."""

import json
from urllib.parse import parse_qs, quote

import pytest
from cql2 import Expr
from starlette.datastructures import QueryParams
from utils import parse_query_string

from stac_auth_proxy.utils.filters import (
    InvalidFilterRequestError,
    append_body_filter,
    append_qs_filter,
)
from stac_auth_proxy.utils.requests import (
    extract_variables,
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


ALLOWED = Expr("collection = 'allowed'")
SMUGGLED = "id = 'a&filter=id IS NOT NULL&x='"


@pytest.mark.parametrize(
    "qs, expected",
    [
        pytest.param(
            f"filter={quote(SMUGGLED)}&filter-lang=cql2-text".encode(),
            {
                "filter": [(ALLOWED + Expr(SMUGGLED)).to_text()],
                "filter-lang": ["cql2-text"],
            },
            id="delimiters_in_value",
        ),
        pytest.param(
            b"a%26filter%3Dtrue%26b=1",
            {
                "a&filter=true&b": ["1"],
                "filter": [ALLOWED.to_text()],
                "filter-lang": ["cql2-text"],
            },
            id="delimiters_in_name",
        ),
        pytest.param(
            b"x=#&collections=public",
            {
                "x": ["#"],
                "collections": ["public"],
                "filter": [ALLOWED.to_text()],
                "filter-lang": ["cql2-text"],
            },
            id="raw_hash_in_query",
        ),
        pytest.param(
            b"q=&collections=a+b%2Bc",
            {
                "q": [""],
                "collections": ["a b+c"],
                "filter": [ALLOWED.to_text()],
                "filter-lang": ["cql2-text"],
            },
            id="blank_and_plus",
        ),
        pytest.param(
            b"filter-lang=",
            {"filter": [ALLOWED.to_text()], "filter-lang": ["cql2-text"]},
            id="blank_filter_lang_defaults_to_text",
        ),
        pytest.param(
            b"filter=&filter-lang=cql2-text",
            {"filter": [ALLOWED.to_text()], "filter-lang": ["cql2-text"]},
            id="blank_filter_ignored",
        ),
    ],
)
def test_append_qs_filter(qs, expected):
    """The forwarded params are exactly those filter factories saw, plus the filter."""
    out = append_qs_filter(qs, ALLOWED).decode()
    assert parse_qs(out, keep_blank_values=True) == expected
    # matches what filter factories received (dict(request.query_params))
    assert {
        k: v for k, v in QueryParams(out).items() if not k.startswith("filter")
    } == {k: v for k, v in dict(QueryParams(qs)).items() if not k.startswith("filter")}


@pytest.mark.parametrize(
    "qs",
    [
        # upstreams disagree on which of repeated values wins
        b"collections=private&collections=public",
        b"filter=true&filter=false",
        # look-alikes some upstreams read in place of the proxy's filter params
        b"FILTER=true",
        b"Filter-Lang=cql2-json",
        b"filter_lang=cql2-json",
        b"filter%5Bop%5D=x",
        b"filter%00=true",
        # would change how the upstream reads the proxy's filter
        b"filter-crs=http://www.opengis.net/def/crs/EPSG/0/3857",
        b"filter_crs=x",
    ],
)
def test_append_qs_filter_rejects_ambiguous_params(qs):
    """Params that could change which filter the upstream applies are rejected."""
    with pytest.raises(InvalidFilterRequestError):
        append_qs_filter(qs, ALLOWED)


@pytest.mark.parametrize(
    "value, expected",
    [
        (True, True),
        # a bare `false` could be dropped by a lenient upstream (`if filter:`)
        (False, {"op": "not", "args": [True]}),
    ],
)
def test_append_qs_filter_scalar_cql2_json(value, expected):
    """A bare boolean CQL2-JSON filter is sent as truthy JSON, not Python's True/False."""
    out = append_qs_filter(b"filter-lang=cql2-json", Expr(value)).decode()
    [sent] = parse_qs(out)["filter"]
    assert json.loads(sent) == expected
    assert Expr(json.loads(sent)).matches({}) is value


@pytest.mark.parametrize(
    "body, proxy_filter, expected",
    [
        pytest.param(
            {"filter": False},
            ALLOWED,
            (ALLOWED + Expr(False)).to_json(),
            id="client_false_kept",
        ),
        pytest.param(
            {}, Expr(False), {"op": "not", "args": [True]}, id="proxy_false_truthy"
        ),
        pytest.param(
            {"filter-lang": ""}, ALLOWED, ALLOWED.to_json(), id="blank_filter_lang"
        ),
    ],
)
def test_append_body_filter(body, proxy_filter, expected):
    """Body filters are combined without dropping falsy values."""
    out = append_body_filter(body, proxy_filter)
    assert out["filter"] == expected
    assert out["filter-lang"] == "cql2-json"


@pytest.mark.parametrize(
    "body", [{"filter-crs": "x"}, {"FILTER": True}, {"filter_lang": "cql2-text"}]
)
def test_append_body_filter_rejects_ambiguous_params(body):
    """Body params that could change which filter the upstream applies are rejected."""
    with pytest.raises(InvalidFilterRequestError):
        append_body_filter(body, ALLOWED)


def test_append_qs_filter_keeps_geometry_compact():
    """Reserved characters without meaning in a query value are not escaped."""
    polygon = {
        "op": "s_intersects",
        "args": [
            {"property": "geometry"},
            {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        ],
    }
    out = append_qs_filter(b"filter-lang=cql2-json", Expr(polygon)).decode()
    for escaped in ("%2C", "%3A", "%5B", "%5D"):  # , : [ ]
        assert escaped not in out
    assert json.loads(parse_qs(out)["filter"][0]) == Expr(polygon).to_json()
