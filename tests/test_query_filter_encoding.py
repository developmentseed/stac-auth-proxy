"""Tests that the CQL2 filter appended to GET query strings reaches the upstream intact."""

from urllib.parse import parse_qsl

import pytest
from cql2 import Expr
from fastapi.testclient import TestClient
from utils import AppFactory

from stac_auth_proxy.utils.filters import append_qs_filter

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
    default_public=True,
    items_filter={
        "cls": "stac_auth_proxy.filters:Template",
        "args": ["collection = 'allowed'"],
    },
    collections_filter={
        "cls": "stac_auth_proxy.filters:Template",
        "args": ["id = 'allowed'"],
    },
)

ITEMS_FILTER = "(collection = 'allowed')"
COLLECTIONS_FILTER = "(id = 'allowed')"


def _forwarded_params(mock_upstream) -> list[tuple[str, str]]:
    [request] = mock_upstream.call_args[0]
    query = request.url.query.decode("ascii")
    assert "#" not in query
    return parse_qsl(query, keep_blank_values=True)


@pytest.mark.parametrize(
    "target, expected",
    [
        (
            "/search?limit=100%23",
            [("filter", ITEMS_FILTER), ("filter-lang", "cql2-text"), ("limit", "100#")],
        ),
        (
            "/collections/c/items?limit=1%23",
            [("filter", ITEMS_FILTER), ("filter-lang", "cql2-text"), ("limit", "1#")],
        ),
        (
            "/collections?x=%23",
            [("filter", COLLECTIONS_FILTER), ("filter-lang", "cql2-text"), ("x", "#")],
        ),
    ],
)
def test_encoded_hash_does_not_drop_filter(
    mock_upstream, source_api_server, target, expected
):
    """A client-encoded '#' must not be decoded into a fragment that truncates the filter."""
    TestClient(app_factory(upstream_url=source_api_server)).get(target)
    assert _forwarded_params(mock_upstream) == expected


def test_encoded_delimiters_cannot_inject_filter(mock_upstream, source_api_server):
    """A client-encoded '&filter=' must stay inside its value, not become a second filter."""
    TestClient(app_factory(upstream_url=source_api_server)).get(
        "/search?filter=true&z=%26filter%3Dtrue"
    )
    params = _forwarded_params(mock_upstream)
    assert [v for k, v in params if k == "filter"] == [f"({ITEMS_FILTER} AND true)"]
    assert ("z", "&filter=true") in params


def test_non_ascii_value(mock_upstream, source_api_server):
    """Percent-encoded non-ASCII values are forwarded re-encoded rather than raising."""
    response = TestClient(app_factory(upstream_url=source_api_server)).get(
        "/search?q=%C3%BC"
    )
    assert response.status_code == 200
    assert ("q", "ü") in _forwarded_params(mock_upstream)


def test_encoded_plus_is_preserved(mock_upstream, source_api_server):
    """A client-encoded '+' must not be forwarded as a literal '+' (read as a space)."""
    TestClient(app_factory(upstream_url=source_api_server)).get(
        "/search?datetime=2020-01-01T00:00:00%2B01:00"
    )
    assert ("datetime", "2020-01-01T00:00:00+01:00") in _forwarded_params(mock_upstream)


def test_raw_utf8_query_encoded_once():
    """Raw UTF-8 bytes in the query are forwarded like their percent-encoded form."""
    raw = append_qs_filter("q=café&r=caf%C3%A9".encode(), Expr("a = 'b'"))
    assert raw.endswith(b"&q=caf%C3%A9&r=caf%C3%A9")
