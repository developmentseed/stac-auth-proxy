"""Tests for AuthenticationExtensionMiddleware."""

import pytest
from starlette.datastructures import Headers
from starlette.requests import Request

from stac_auth_proxy.config import EndpointMethods
from stac_auth_proxy.middleware.AuthenticationExtensionMiddleware import (
    AuthenticationExtensionMiddleware,
)


@pytest.fixture
def middleware():
    """Create a test instance of the middleware."""
    return AuthenticationExtensionMiddleware(
        app=None,  # We don't need the actual app for these tests
        default_public=True,
        private_endpoints=EndpointMethods(),
        public_endpoints=EndpointMethods(),
        auth_scheme_name="test_auth",
        auth_scheme={},
    )


@pytest.fixture
def request_scope():
    """Create a basic request scope."""
    return {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
    }


@pytest.fixture(params=["application/json", "application/geo+json"])
def json_headers(request):
    """Create headers with JSON content type."""
    return Headers({"content-type": request.param})


@pytest.fixture
def oidc_metadata():
    """Create test OIDC metadata."""
    return {
        "authorization_endpoint": "https://auth.example.com/auth",
        "token_endpoint": "https://auth.example.com/token",
        "scopes_supported": ["openid", "profile"],
    }


def test_should_transform_response_valid_paths(middleware, request_scope, json_headers):
    """Test that valid STAC paths are transformed."""
    valid_paths = [
        "/",
        "/collections",
        "/collections/test-collection",
        "/collections/test-collection/items",
        "/collections/test-collection/items/test-item",
        "/search",
    ]

    for path in valid_paths:
        request_scope["path"] = path
        request = Request(request_scope)
        assert middleware.should_transform_response(request, json_headers)


def test_should_transform_response_invalid_paths(
    middleware, request_scope, json_headers
):
    """Test that invalid paths are not transformed."""
    invalid_paths = [
        "/api",
        "/collections/test-collection/items/test-item/assets",
        "/random",
    ]

    for path in invalid_paths:
        request_scope["path"] = path
        request = Request(request_scope)
        assert not middleware.should_transform_response(request, json_headers)


def test_should_transform_response_invalid_content_type(middleware, request_scope):
    """Test that non-JSON content types are not transformed."""
    request = Request(request_scope)
    headers = Headers({"content-type": "text/html"})
    assert not middleware.should_transform_response(request, headers)


def test_transform_json_catalog(middleware, request_scope, oidc_metadata):
    """Test transforming a STAC catalog."""
    request = Request(request_scope)
    request.state.oidc_metadata = oidc_metadata

    catalog = {
        "stac_version": "1.0.0",
        "id": "test-catalog",
        "description": "Test catalog",
        "links": [
            {"rel": "self", "href": "/"},
            {"rel": "root", "href": "/"},
        ],
    }

    transformed = middleware.transform_json(catalog, request)

    assert "stac_extensions" in transformed
    assert middleware.extension_url in transformed["stac_extensions"]
    assert "auth:schemes" in transformed
    assert "test_auth" in transformed["auth:schemes"]

    scheme = transformed["auth:schemes"]["test_auth"]
    assert scheme["type"] == "oauth2"
    assert (
        scheme["flows"]["authorizationCode"]["authorizationUrl"]
        == oidc_metadata["authorization_endpoint"]
    )
    assert (
        scheme["flows"]["authorizationCode"]["tokenUrl"]
        == oidc_metadata["token_endpoint"]
    )
    assert "openid" in scheme["flows"]["authorizationCode"]["scopes"]
    assert "profile" in scheme["flows"]["authorizationCode"]["scopes"]


def test_transform_json_collection(middleware, request_scope, oidc_metadata):
    """Test transforming a STAC collection."""
    request = Request(request_scope)
    request.state.oidc_metadata = oidc_metadata

    collection = {
        "stac_version": "1.0.0",
        "type": "Collection",
        "id": "test-collection",
        "description": "Test collection",
        "links": [
            {"rel": "self", "href": "/collections/test-collection"},
            {"rel": "items", "href": "/collections/test-collection/items"},
        ],
    }

    transformed = middleware.transform_json(collection, request)

    assert "stac_extensions" in transformed
    assert middleware.extension_url in transformed["stac_extensions"]
    assert "auth:schemes" in transformed
    assert "test_auth" in transformed["auth:schemes"]


def test_transform_json_item(middleware, request_scope, oidc_metadata):
    """Test transforming a STAC item."""
    request = Request(request_scope)
    request.state.oidc_metadata = oidc_metadata

    item = {
        "stac_version": "1.0.0",
        "type": "Feature",
        "id": "test-item",
        "properties": {},
        "links": [
            {"rel": "self", "href": "/collections/test-collection/items/test-item"},
            {"rel": "collection", "href": "/collections/test-collection"},
        ],
    }

    transformed = middleware.transform_json(item, request)

    assert "stac_extensions" in transformed
    assert middleware.extension_url in transformed["stac_extensions"]
    assert "auth:schemes" in transformed["properties"]
    assert "test_auth" in transformed["properties"]["auth:schemes"]


def test_transform_json_missing_oidc_metadata(middleware, request_scope):
    """Test transforming when OIDC metadata is missing."""
    request = Request(request_scope)

    catalog = {
        "stac_version": "1.0.0",
        "id": "test-catalog",
        "description": "Test catalog",
    }

    transformed = middleware.transform_json(catalog, request)
    # Should return unchanged when OIDC metadata is missing
    assert transformed == catalog
