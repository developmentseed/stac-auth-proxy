"""Tests for AuthenticationExtensionMiddleware."""

import pytest
from starlette.requests import Request

from stac_auth_proxy.config import EndpointMethods
from stac_auth_proxy.middleware.AuthenticationExtensionMiddleware import (
    AuthenticationExtensionMiddleware,
)


@pytest.fixture
def oidc_discovery_url():
    """Create test OIDC discovery URL."""
    return "https://auth.example.com/discovery"


@pytest.fixture
def middleware(oidc_discovery_url):
    """Create a test instance of the middleware."""
    return AuthenticationExtensionMiddleware(
        app=None,  # We don't need the actual app for these tests
        default_public=True,
        private_endpoints=EndpointMethods(),
        public_endpoints=EndpointMethods(),
        oidc_discovery_url=oidc_discovery_url,
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


@pytest.fixture(params=[b"application/json", b"application/geo+json"])
def initial_message(request):
    """Create headers with JSON content type."""
    return {
        "type": "http.response.start",
        "status": 200,
        "headers": [
            (b"date", b"Mon, 07 Apr 2025 06:55:37 GMT"),
            (b"server", b"uvicorn"),
            (b"content-length", b"27642"),
            (b"content-type", request.param),
            (b"x-upstream-time", b"0.063"),
        ],
    }


def test_should_transform_response_valid_paths(
    middleware, request_scope, initial_message
):
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
        assert middleware.should_transform_response(request, initial_message)


def test_should_transform_response_invalid_paths(
    middleware, request_scope, initial_message
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
        assert not middleware.should_transform_response(request, initial_message)


def test_should_transform_response_invalid_content_type(middleware, request_scope):
    """Test that non-JSON content types are not transformed."""
    request = Request(request_scope)
    assert not middleware.should_transform_response(
        request,
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"date", b"Mon, 07 Apr 2025 06:55:37 GMT"),
                (b"server", b"uvicorn"),
                (b"content-length", b"27642"),
                (b"content-type", b"text/html"),
                (b"x-upstream-time", b"0.063"),
            ],
        },
    )


def test_transform_json_catalog(middleware, request_scope, oidc_discovery_url):
    """Test transforming a STAC catalog."""
    request = Request(request_scope)

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
    assert scheme["type"] == "openIdConnect"
    assert scheme["openIdConnectUrl"] == oidc_discovery_url


def test_transform_json_collection(middleware, request_scope):
    """Test transforming a STAC collection."""
    request = Request(request_scope)

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


def test_transform_json_item(middleware, request_scope):
    """Test transforming a STAC item."""
    request = Request(request_scope)

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
