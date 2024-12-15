"""Tests for Jinja2 CQL2 filter."""

from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient
from utils import AppFactory

from tests.utils import single_chunk_async_stream_response

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
    default_public=False,
)


def test_collections_filter_contained_by_token(
    mock_upstream, source_api_server, token_builder
):
    """Test that the collections filter is applied correctly."""
    # Mock response from upstream API
    mock_upstream.return_value = single_chunk_async_stream_response(b"{}")

    app = app_factory(
        upstream_url=source_api_server,
        collections_filter={
            "cls": "stac_auth_proxy.filters.Template",
            "args": [
                "A_CONTAINEDBY(id, ('{{ token.collections | join(\"', '\") }}' ))"
            ],
        },
    )

    auth_token = token_builder({"collections": ["foo", "bar"]})
    client = TestClient(app, headers={"Authorization": f"Bearer {auth_token}"})
    response = client.get("/collections")

    assert response.status_code == 200
    assert mock_upstream.call_count == 1
    [r] = mock_upstream.call_args[0]
    assert parse_qs(r.url.query.decode()) == {
        "filter": ["a_containedby(id, ('foo', 'bar'))"]
    }


@pytest.mark.parametrize(
    "authenticated, expected_filter",
    [
        (True, "true"),
        (False, "(private = false)"),
    ],
)
def test_collections_filter_private_and_public(
    mock_upstream, source_api_server, token_builder, authenticated, expected_filter
):
    """Test that filter can be used for private/public collections."""
    # Mock response from upstream API
    mock_upstream.return_value = single_chunk_async_stream_response(b"{}")

    app = app_factory(
        upstream_url=source_api_server,
        collections_filter={
            "cls": "stac_auth_proxy.filters.Template",
            "args": ["{{ '(private = false)' if token is none else true }}"],
        },
        default_public=True,
    )

    client = TestClient(
        app,
        headers=(
            {"Authorization": f"Bearer {token_builder({})}"} if authenticated else {}
        ),
    )
    response = client.get("/collections")

    assert response.status_code == 200
    assert mock_upstream.call_count == 1
    [r] = mock_upstream.call_args[0]
    assert parse_qs(r.url.query.decode()) == {"filter": [expected_filter]}
