"""Tests for CEL guard."""

import pytest
from fastapi.testclient import TestClient
from utils import AppFactory

app_factory = AppFactory(
    oidc_discovery_url="https://samples.auth0.com/.well-known/openid-configuration",
    default_public=False,
)


@pytest.mark.parametrize(
    "endpoint, expected_status_code",
    [
        ("/", 403),
        ("/?foo=xyz", 403),
        ("/?bar=foo", 403),
        ("/?foo=bar", 200),
        ("/?foo=xyz&foo=bar", 200),  # Only the last value is checked
        ("/?foo=bar&foo=xyz", 403),  # Only the last value is checked
    ],
)
def test_guard_query_params(
    source_api_server,
    token_builder,
    endpoint,
    expected_status_code,
):
    app = app_factory(
        upstream_url=source_api_server,
        guard={
            "cls": "stac_auth_proxy.guards.cel",
            "args": ('has(req.query_params.foo) && req.query_params.foo == "bar"',),
        },
    )
    client = TestClient(app, headers={"Authorization": f"Bearer {token_builder({})}"})
    response = client.get(endpoint)
    assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "token, expected_status_code",
    [
        ({"foo": "bar"}, 403),
        ({"collections": []}, 403),
        ({"collections": ["foo", "bar"]}, 403),
        ({"collections": ["xyz"]}, 200),
        ({"collections": ["foo", "xyz"]}, 200),
    ],
)
def test_guard_auth_token(
    source_api_server,
    token_builder,
    token,
    expected_status_code,
):
    app = app_factory(
        upstream_url=source_api_server,
        guard={
            "cls": "stac_auth_proxy.guards.cel",
            "args": (
                """
                has(req.path_params.collection_id) && has(token.collections) &&
                req.path_params.collection_id in (token.collections)
                """,
            ),
        },
    )
    client = TestClient(
        app, headers={"Authorization": f"Bearer {token_builder(token)}"}
    )
    response = client.get("/collections/xyz")
    assert response.status_code == expected_status_code
