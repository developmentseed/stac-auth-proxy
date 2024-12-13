"""Tests for Jinja2 CQL2 filter."""

import pytest
from fastapi.testclient import TestClient
from utils import AppFactory

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
    default_public=False,
)


def test_collections_filter_contained_by_token(source_api_server, token_builder):
    """"""
    app = app_factory(
        upstream_url=source_api_server,
        collections_filter={
            "cls": "stac_auth_proxy.filters.Template",
            "args": [
                "A_CONTAINEDBY(id, ( '{{ token.collections | join(\"', '\") }}' ))"
            ],
        },
    )
    client = TestClient(
        app,
        headers={
            "Authorization": f"Bearer {token_builder({"collections": ["foo", "bar"]})}"
        },
    )
    response = client.get("/collections")
    assert response.status_code == 200

    # TODO: We need to verify that the upstream API was called with an applied filter
