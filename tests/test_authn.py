"""Test authentication cases for the proxy app."""

import pytest
from fastapi.testclient import TestClient
from utils import AppFactory

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
    default_public=False,
    public_endpoints={},
    private_endpoints={},
)


@pytest.mark.parametrize(
    "path,method",
    [
        ("/", "GET"),
        ("/conformance", "GET"),
        ("/queryables", "GET"),
        ("/search", "GET"),
        ("/search", "POST"),
        ("/collections", "GET"),
        ("/collections", "POST"),
        ("/collections/example-collection", "GET"),
        ("/collections/example-collection", "PUT"),
        ("/collections/example-collection", "DELETE"),
        ("/collections/example-collection/items", "GET"),
        ("/collections/example-collection/items", "POST"),
        ("/collections/example-collection/items/example-item", "GET"),
        ("/collections/example-collection/items/example-item", "PUT"),
        ("/collections/example-collection/items/example-item", "DELETE"),
        ("/collections/example-collection/bulk_items", "POST"),
        ("/api.html", "GET"),
        ("/api", "GET"),
    ],
)
def test_default_public_false(source_api_server, path, method, token_builder):
    """Private endpoints permit access with a valid token."""
    test_app = app_factory(upstream_url=source_api_server)
    valid_auth_token = token_builder({})

    client = TestClient(test_app)
    response = client.request(method=method, url=path, headers={})
    assert response.status_code == 403

    response = client.request(
        method=method, url=path, headers={"Authorization": f"Bearer {valid_auth_token}"}
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "token_scopes, private_endpoints, path, method, expected_permitted",
    [
        pytest.param(
            "",
            {r"^/*": [("POST", ["collections:create"])]},
            "/collections",
            "POST",
            False,
            id="empty scopes + private endpoint",
        ),
        pytest.param(
            "openid profile collections:createbutnotcreate",
            {r"^/*": [("POST", ["collections:create"])]},
            "/collections",
            "POST",
            False,
            id="invalid scopes + private endpoint",
        ),
        pytest.param(
            "openid profile collections:create somethingelse",
            {r"^/*": [("POST", [])]},
            "/collections",
            "POST",
            True,
            id="valid scopes + private endpoint without required scopes",
        ),
        pytest.param(
            "openid",
            {r"^/collections/.*/items$": [("POST", ["collections:create"])]},
            "/collections",
            "GET",
            True,
            id="accessing public endpoint with private endpoint required scopes",
        ),
    ],
)
def test_scopes(
    source_api_server,
    token_builder,
    token_scopes,
    private_endpoints,
    path,
    method,
    expected_permitted,
):
    """Private endpoints permit access with a valid token."""
    test_app = app_factory(
        upstream_url=source_api_server,
        default_public=True,
        private_endpoints=private_endpoints,
    )
    valid_auth_token = token_builder({"scope": token_scopes})
    client = TestClient(test_app)

    response = client.request(
        method=method,
        url=path,
        headers={"Authorization": f"Bearer {valid_auth_token}"},
    )
    expected_status_code = 200 if expected_permitted else 401
    assert response.status_code == expected_status_code
