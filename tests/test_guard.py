"""Tests for OpenAPI spec handling."""

import pytest
from fastapi.testclient import TestClient
from utils import AppFactory

app_factory = AppFactory(
    oidc_discovery_url="https://samples.auth0.com/.well-known/openid-configuration",
    default_public=False,
)


import pytest
from unittest.mock import patch, MagicMock


# Fixture to patch OpenIdConnectAuth and mock valid_token_dependency
@pytest.fixture
def skip_auth():
    with patch("eoapi.auth_utils.OpenIdConnectAuth") as MockClass:
        # Create a mock instance
        mock_instance = MagicMock()
        # Set the return value of `valid_token_dependency`
        mock_instance.valid_token_dependency.return_value = "constant"
        # Assign the mock instance to the patched class's return value
        MockClass.return_value = mock_instance

        # Yield the mock instance for use in tests
        yield mock_instance


@pytest.mark.parametrize(
    "endpoint, expected_status_code",
    [
        ("/", 403),
        ("/?foo=xyz", 403),
        ("/?foo=bar", 200),
    ],
)
def test_guard_query_params(
    source_api_server,
    token_builder,
    endpoint,
    expected_status_code,
):
    """When no OpenAPI spec endpoint is set, the proxied OpenAPI spec is unaltered."""
    app = app_factory(
        upstream_url=source_api_server,
        guard={
            "cls": "stac_auth_proxy.guards.cel.Cel",
            "kwargs": {
                "expression": '("foo" in req.query_params) && req.query_params.foo == "bar"'
            },
        },
    )
    client = TestClient(app, headers={"Authorization": f"Bearer {token_builder({})}"})
    response = client.get(endpoint)
    assert response.status_code == expected_status_code
