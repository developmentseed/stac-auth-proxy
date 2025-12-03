"""Basic test cases for the proxy app."""

import pytest
from fastapi.testclient import TestClient
from utils import AppFactory

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration"
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
        ("/collections", "POST", 401),
        ("/collections/example-collection", "GET", 200),
        ("/collections/example-collection", "PUT", 401),
        ("/collections/example-collection", "DELETE", 401),
        ("/collections/example-collection/items", "GET", 200),
        ("/collections/example-collection/items", "POST", 401),
        ("/collections/example-collection/items/example-item", "GET", 200),
        ("/collections/example-collection/items/example-item", "PUT", 401),
        ("/collections/example-collection/items/example-item", "DELETE", 401),
        ("/collections/example-collection/bulk_items", "POST", 401),
        ("/api.html", "GET", 200),
        ("/api", "GET", 200),
    ],
)
def test_default_public_true(source_api_server, path, method, expected_status):
    """
    When default_public=true and private_endpoints are set, all endpoints should be
    public except for transaction endpoints.
    """
    test_app = app_factory(
        upstream_url=source_api_server,
        public_endpoints={},
        private_endpoints={
            r"^/collections$": ["POST"],
            r"^/collections/([^/]+)$": ["PUT", "PATCH", "DELETE"],
            r"^/collections/([^/]+)/items$": ["POST"],
            r"^/collections/([^/]+)/items/([^/]+)$": ["PUT", "PATCH", "DELETE"],
            r"^/collections/([^/]+)/bulk_items$": ["POST"],
        },
        default_public=True,
    )
    client = TestClient(test_app)
    response = client.request(method=method, url=path)
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "path,method,expected_status",
    [
        ("/", "GET", 401),
        ("/conformance", "GET", 401),
        ("/queryables", "GET", 401),
        ("/search", "GET", 401),
        ("/search", "POST", 401),
        ("/collections", "GET", 401),
        ("/collections", "POST", 401),
        ("/collections/example-collection", "GET", 401),
        ("/collections/example-collection", "PUT", 401),
        ("/collections/example-collection", "DELETE", 401),
        ("/collections/example-collection/items", "GET", 401),
        ("/collections/example-collection/items", "POST", 401),
        ("/collections/example-collection/items/example-item", "GET", 401),
        ("/collections/example-collection/items/example-item", "PUT", 401),
        ("/collections/example-collection/items/example-item", "DELETE", 401),
        ("/collections/example-collection/bulk_items", "POST", 401),
        ("/api.html", "GET", 200),
        ("/api", "GET", 200),
    ],
)
def test_default_public_false(source_api_server, path, method, expected_status):
    """
    When default_public=false and private_endpoints aren't set, all endpoints should be
    public except for transaction endpoints.
    """
    test_app = app_factory(
        upstream_url=source_api_server,
        public_endpoints={"/api.html": ["GET"], "/api": ["GET"]},
        private_endpoints={},
        default_public=False,
    )
    client = TestClient(test_app)
    response = client.request(method=method, url=path)
    assert response.status_code == expected_status
