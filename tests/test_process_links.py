"""Tests for ProcessLinksMiddleware."""

import pytest
from starlette.requests import Request

from stac_auth_proxy.middleware.ProcessLinksMiddleware import ProcessLinksMiddleware


@pytest.fixture
def middleware():
    """Create a test instance of the middleware."""
    return ProcessLinksMiddleware(
        app=None,  # We don't need the actual app for these tests
        upstream_url="http://upstream.example.com/api",
        root_path="/proxy",
    )


@pytest.fixture
def request_scope():
    """Create a test request scope."""
    return {
        "type": "http",
        "path": "/test",
        "headers": [
            (b"host", b"proxy.example.com"),
            (b"content-type", b"application/json"),
        ],
    }


def test_should_transform_response_json(middleware, request_scope):
    """Test that JSON responses are transformed."""
    request = Request(request_scope)
    assert middleware.should_transform_response(request, request_scope)


def test_should_transform_response_geojson(middleware, request_scope):
    """Test that GeoJSON responses are transformed."""
    request_scope["headers"] = [
        (b"host", b"proxy.example.com"),
        (b"content-type", b"application/geo+json"),
    ]
    request = Request(request_scope)
    assert middleware.should_transform_response(request, request_scope)


def test_should_transform_response_non_json(middleware, request_scope):
    """Test that non-JSON responses are not transformed."""
    request_scope["headers"] = [
        (b"host", b"proxy.example.com"),
        (b"content-type", b"text/plain"),
    ]
    request = Request(request_scope)
    assert not middleware.should_transform_response(request, request_scope)


def test_transform_json_with_upstream_path(middleware, request_scope):
    """Test transforming links with upstream URL path."""
    request = Request(request_scope)

    data = {
        "links": [
            {"rel": "self", "href": "http://proxy.example.com/api/collections"},
            {"rel": "root", "href": "http://proxy.example.com/api"},
        ]
    }

    transformed = middleware.transform_json(data, request)

    assert (
        transformed["links"][0]["href"] == "http://proxy.example.com/proxy/collections"
    )
    assert transformed["links"][1]["href"] == "http://proxy.example.com/proxy"


def test_transform_json_without_upstream_path(middleware, request_scope):
    """Test transforming links without upstream URL path."""
    middleware = ProcessLinksMiddleware(
        app=None, upstream_url="http://upstream.example.com", root_path="/proxy"
    )
    request = Request(request_scope)

    data = {
        "links": [
            {"rel": "self", "href": "http://proxy.example.com/collections"},
            {"rel": "root", "href": "http://proxy.example.com/"},
        ]
    }

    transformed = middleware.transform_json(data, request)

    assert (
        transformed["links"][0]["href"] == "http://proxy.example.com/proxy/collections"
    )
    assert transformed["links"][1]["href"] == "http://proxy.example.com/proxy/"


def test_transform_json_without_root_path(middleware, request_scope):
    """Test transforming links without root path."""
    middleware = ProcessLinksMiddleware(
        app=None, upstream_url="http://upstream.example.com/api", root_path=None
    )
    request = Request(request_scope)

    data = {
        "links": [
            {"rel": "self", "href": "http://proxy.example.com/api/collections"},
            {"rel": "root", "href": "http://proxy.example.com/api"},
        ]
    }

    transformed = middleware.transform_json(data, request)

    assert transformed["links"][0]["href"] == "http://proxy.example.com/collections"
    assert transformed["links"][1]["href"] == "http://proxy.example.com"


def test_transform_json_different_host(middleware, request_scope):
    """Test that links with different hostnames are not transformed."""
    request = Request(request_scope)

    data = {
        "links": [
            {"rel": "self", "href": "http://other.example.com/api/collections"},
            {"rel": "root", "href": "http://other.example.com/api"},
        ]
    }

    transformed = middleware.transform_json(data, request)

    assert transformed["links"][0]["href"] == "http://other.example.com/api/collections"
    assert transformed["links"][1]["href"] == "http://other.example.com/api"


def test_transform_json_invalid_link(middleware, request_scope):
    """Test that invalid links are handled gracefully."""
    request = Request(request_scope)

    data = {
        "links": [
            {"rel": "self", "href": "not-a-url"},
            {"rel": "root", "href": "http://proxy.example.com/api"},
        ]
    }

    transformed = middleware.transform_json(data, request)

    assert transformed["links"][0]["href"] == "not-a-url"
    assert transformed["links"][1]["href"] == "http://proxy.example.com/proxy"


def test_transform_json_nested_links(middleware, request_scope):
    """Test transforming links in nested STAC objects."""
    request = Request(request_scope)

    data = {
        "links": [
            {"rel": "self", "href": "http://proxy.example.com/api"},
        ],
        "collections": [
            {
                "id": "test-collection",
                "links": [
                    {
                        "rel": "self",
                        "href": "http://proxy.example.com/api/collections/test-collection",
                    },
                    {
                        "rel": "items",
                        "href": "http://proxy.example.com/api/collections/test-collection/items",
                    },
                ],
            }
        ],
    }

    transformed = middleware.transform_json(data, request)

    assert transformed["links"][0]["href"] == "http://proxy.example.com/proxy"
    assert (
        transformed["collections"][0]["links"][0]["href"]
        == "http://proxy.example.com/proxy/collections/test-collection"
    )
    assert (
        transformed["collections"][0]["links"][1]["href"]
        == "http://proxy.example.com/proxy/collections/test-collection/items"
    )
