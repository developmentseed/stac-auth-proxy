"""Basic test cases for the proxy app."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stac_auth_proxy import Settings, create_app


@pytest.fixture(scope="module")
def test_app(source_api_server: str) -> FastAPI:
    """Fixture for the proxy app, pointing to the source API."""
    return create_app(
        Settings.model_validate(
            {
                "upstream_url": source_api_server,
                "oidc_discovery_url": "https://samples.auth0.com/.well-known/openid-configuration",
                "default_public": False,
            },
        )
    )


@pytest.mark.parametrize(
    "path,method,expected_status",
    [
        ("/", "GET", 200),
        ("/conformance", "GET", 200),
        ("/queryables", "GET", 200),
        ("/search", "GET", 200),
        ("/search", "POST", 200),
        ("/collections", "GET", 200),
        ("/collections", "POST", 403),
        ("/collections/example-collection", "GET", 200),
        ("/collections/example-collection", "PUT", 403),
        ("/collections/example-collection", "DELETE", 403),
        ("/collections/example-collection/items", "GET", 200),
        ("/collections/example-collection/items", "POST", 403),
        ("/collections/example-collection/items/example-item", "GET", 200),
        ("/collections/example-collection/items/example-item", "PUT", 403),
        ("/collections/example-collection/items/example-item", "DELETE", 403),
        ("/collections/example-collection/bulk_items", "POST", 403),
        ("/api.html", "GET", 200),
        ("/api", "GET", 200),
    ],
)
def test_default_public_true(source_api_server, path, method, expected_status):
    """
    When default_public=true and private_endpoints aren't set, all endpoints should be
    public except for transaction endpoints.
    """
    test_app = create_app(
        Settings.model_validate(
            {
                "upstream_url": source_api_server,
                "oidc_discovery_url": "https://samples.auth0.com/.well-known/openid-configuration",
                "default_public": True,
            },
        )
    )
    client = TestClient(test_app)
    response = client.request(method=method, url=path)
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "path,method,expected_status",
    [
        ("/", "GET", 403),
        ("/conformance", "GET", 403),
        ("/queryables", "GET", 403),
        ("/search", "GET", 403),
        ("/search", "POST", 403),
        ("/collections", "GET", 403),
        ("/collections", "POST", 403),
        ("/collections/example-collection", "GET", 403),
        ("/collections/example-collection", "PUT", 403),
        ("/collections/example-collection", "DELETE", 403),
        ("/collections/example-collection/items", "GET", 403),
        ("/collections/example-collection/items", "POST", 403),
        ("/collections/example-collection/items/example-item", "GET", 403),
        ("/collections/example-collection/items/example-item", "PUT", 403),
        ("/collections/example-collection/items/example-item", "DELETE", 403),
        ("/collections/example-collection/bulk_items", "POST", 403),
        ("/api.html", "GET", 200),
        ("/api", "GET", 200),
    ],
)
def test_default_public_false(source_api_server, path, method, expected_status):
    """
    When default_public=false and private_endpoints aren't set, all endpoints should be
    public except for transaction endpoints.
    """
    test_app = create_app(
        Settings.model_validate(
            {
                "upstream_url": source_api_server,
                "oidc_discovery_url": "https://samples.auth0.com/.well-known/openid-configuration",
                "default_public": False,
            },
        )
    )
    client = TestClient(test_app)
    response = client.request(method=method, url=path)
    assert response.status_code == expected_status
