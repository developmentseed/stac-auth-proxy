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


def test_transform_json_with_null_stac_extensions(
    middleware, request_scope, oidc_discovery_url
):
    """Test transforming when stac_extensions is None."""
    request = Request(request_scope)

    catalog = {
        "stac_version": "1.0.0",
        "id": "test-catalog",
        "description": "Test catalog",
        "stac_extensions": None,
    }

    transformed = middleware.transform_json(catalog, request)

    assert "stac_extensions" in transformed
    assert middleware.extension_url in transformed["stac_extensions"]
    assert "auth:schemes" in transformed
    assert "test_auth" in transformed["auth:schemes"]


@pytest.mark.parametrize(
    "invalid_value",
    [
        "not-a-list",
        42,
        {"key": "value"},
        3.14,
        True,
    ],
)
def test_transform_json_with_invalid_stac_extensions_types(
    middleware, request_scope, oidc_discovery_url, invalid_value
):
    """Test transforming when stac_extensions is an invalid type (string, int, dict, etc)."""
    request = Request(request_scope)

    catalog = {
        "stac_version": "1.0.0",
        "id": "test-catalog",
        "description": "Test catalog",
        "stac_extensions": invalid_value,
    }

    transformed = middleware.transform_json(catalog, request)

    # Should replace invalid value with a proper list
    assert "stac_extensions" in transformed
    assert isinstance(transformed["stac_extensions"], list)
    assert middleware.extension_url in transformed["stac_extensions"]
    assert "auth:schemes" in transformed
    assert "test_auth" in transformed["auth:schemes"]


class TestFilterPathAnnotation:
    """Tests for auth:refs annotation when links match items/collections filter paths."""

    @pytest.fixture
    def middleware_with_items_filter(self, oidc_discovery_url):
        """Middleware with items_filter_path configured."""
        return AuthenticationExtensionMiddleware(
            app=None,
            default_public=True,
            private_endpoints=EndpointMethods(),
            public_endpoints=EndpointMethods(),
            oidc_discovery_url=oidc_discovery_url,
            auth_scheme_name="test_auth",
            items_filter_path=r"^/collections/[^/]+/items$",
        )

    @pytest.fixture
    def middleware_with_collections_filter(self, oidc_discovery_url):
        """Middleware with collections_filter_path configured."""
        return AuthenticationExtensionMiddleware(
            app=None,
            default_public=True,
            private_endpoints=EndpointMethods(),
            public_endpoints=EndpointMethods(),
            oidc_discovery_url=oidc_discovery_url,
            auth_scheme_name="test_auth",
            collections_filter_path=r"^/collections$",
        )

    @pytest.fixture
    def middleware_with_both_filters(self, oidc_discovery_url):
        """Middleware with both filter paths configured."""
        return AuthenticationExtensionMiddleware(
            app=None,
            default_public=True,
            private_endpoints=EndpointMethods(),
            public_endpoints=EndpointMethods(),
            oidc_discovery_url=oidc_discovery_url,
            auth_scheme_name="test_auth",
            items_filter_path=r"^/collections/[^/]+/items$",
            collections_filter_path=r"^/collections$",
        )

    def test_items_link_annotated_when_items_filter_matches(
        self, middleware_with_items_filter, request_scope
    ):
        """Links to items endpoints get auth:refs when items_filter_path matches."""
        request = Request(request_scope)
        data = {
            "stac_version": "1.0.0",
            "type": "Collection",
            "id": "test",
            "description": "Test",
            "links": [
                {"rel": "self", "href": "/collections/test"},
                {"rel": "items", "href": "/collections/test/items"},
            ],
        }

        transformed = middleware_with_items_filter.transform_json(data, request)

        # The self link should NOT have auth:refs (no private endpoints, default_public=True)
        self_link = next(link for link in transformed["links"] if link["rel"] == "self")
        assert "auth:refs" not in self_link

        # The items link SHOULD have auth:refs because it matches items_filter_path
        items_link = next(
            link for link in transformed["links"] if link["rel"] == "items"
        )
        assert "auth:refs" in items_link
        assert "test_auth" in items_link["auth:refs"]

    def test_collections_link_annotated_when_collections_filter_matches(
        self, middleware_with_collections_filter, request_scope
    ):
        """Links to collections endpoint get auth:refs when collections_filter_path matches."""
        request = Request(request_scope)
        data = {
            "stac_version": "1.0.0",
            "id": "test-catalog",
            "description": "Test catalog",
            "links": [
                {"rel": "self", "href": "/"},
                {"rel": "data", "href": "/collections"},
            ],
        }

        transformed = middleware_with_collections_filter.transform_json(data, request)

        self_link = next(link for link in transformed["links"] if link["rel"] == "self")
        assert "auth:refs" not in self_link

        collections_link = next(
            link for link in transformed["links"] if link["rel"] == "data"
        )
        assert "auth:refs" in collections_link
        assert "test_auth" in collections_link["auth:refs"]

    def test_both_filter_paths_annotated(
        self, middleware_with_both_filters, request_scope
    ):
        """Links matching either filter path get auth:refs."""
        request = Request(request_scope)
        data = {
            "stac_version": "1.0.0",
            "id": "test-catalog",
            "description": "Test catalog",
            "links": [
                {"rel": "self", "href": "/"},
                {"rel": "data", "href": "/collections"},
                {"rel": "items", "href": "/collections/test/items"},
            ],
        }

        transformed = middleware_with_both_filters.transform_json(data, request)

        self_link = next(link for link in transformed["links"] if link["rel"] == "self")
        assert "auth:refs" not in self_link

        collections_link = next(
            link for link in transformed["links"] if link["rel"] == "data"
        )
        assert "auth:refs" in collections_link

        items_link = next(
            link for link in transformed["links"] if link["rel"] == "items"
        )
        assert "auth:refs" in items_link

    def test_non_matching_link_not_annotated(
        self, middleware_with_items_filter, request_scope
    ):
        """Links that don't match filter paths are not annotated when default_public=True."""
        request = Request(request_scope)
        data = {
            "stac_version": "1.0.0",
            "type": "Collection",
            "id": "test",
            "description": "Test",
            "links": [
                {"rel": "self", "href": "/collections/test"},
                {"rel": "root", "href": "/"},
            ],
        }

        transformed = middleware_with_items_filter.transform_json(data, request)

        for link in transformed["links"]:
            assert "auth:refs" not in link

    def test_no_filter_paths_configured(self, middleware, request_scope):
        """Without filter paths, default_public=True means no links get auth:refs."""
        request = Request(request_scope)
        data = {
            "stac_version": "1.0.0",
            "id": "test-catalog",
            "description": "Test catalog",
            "links": [
                {"rel": "self", "href": "/"},
                {"rel": "data", "href": "/collections"},
                {"rel": "items", "href": "/collections/test/items"},
            ],
        }

        transformed = middleware.transform_json(data, request)

        for link in transformed["links"]:
            assert "auth:refs" not in link

    def test_link_method_used_for_matching(self, oidc_discovery_url, request_scope):
        """Link's method property is used when matching against private endpoints."""
        middleware = AuthenticationExtensionMiddleware(
            app=None,
            default_public=True,
            private_endpoints={r"^/collections/[^/]+/items$": ["POST"]},
            public_endpoints=EndpointMethods(),
            oidc_discovery_url=oidc_discovery_url,
            auth_scheme_name="test_auth",
        )
        request = Request(request_scope)
        data = {
            "stac_version": "1.0.0",
            "type": "Collection",
            "id": "test",
            "description": "Test",
            "links": [
                {"rel": "items", "href": "/collections/test/items"},
                {"rel": "create", "href": "/collections/test/items", "method": "POST"},
            ],
        }

        transformed = middleware.transform_json(data, request)

        # GET link should NOT have auth:refs (default_public=True, POST is private not GET)
        get_link = next(link for link in transformed["links"] if link["rel"] == "items")
        assert "auth:refs" not in get_link

        # POST link SHOULD have auth:refs
        post_link = next(
            link for link in transformed["links"] if link["rel"] == "create"
        )
        assert "auth:refs" in post_link
        assert "test_auth" in post_link["auth:refs"]

    def test_filter_path_with_absolute_url(
        self, middleware_with_items_filter, request_scope
    ):
        """Filter path matching works with absolute URLs in link hrefs."""
        request = Request(request_scope)
        data = {
            "stac_version": "1.0.0",
            "type": "Collection",
            "id": "test",
            "description": "Test",
            "links": [
                {
                    "rel": "items",
                    "href": "https://example.com/collections/test/items",
                },
            ],
        }

        transformed = middleware_with_items_filter.transform_json(data, request)

        items_link = transformed["links"][0]
        assert "auth:refs" in items_link
        assert "test_auth" in items_link["auth:refs"]

    def test_filter_path_matches_when_upstream_bakes_root_path(
        self, oidc_discovery_url, request_scope
    ):
        """
        auth:refs is added even when upstream link hrefs already include root_path.

        Regression: some upstreams (e.g. stac-fastapi-pgstac >=6.2) honor the
        Forwarded header's `path` component and produce link hrefs with
        root_path already baked in (e.g. `/stac/collections`). AuthenticationExtensionMiddleware
        runs before ProcessLinksMiddleware, so it must strip root_path before
        applying the filter_path regexes.
        """
        middleware = AuthenticationExtensionMiddleware(
            app=None,
            default_public=True,
            private_endpoints=EndpointMethods(),
            public_endpoints=EndpointMethods(),
            oidc_discovery_url=oidc_discovery_url,
            auth_scheme_name="test_auth",
            items_filter_path=r"^(/collections/([^/]+)/items(/[^/]+)?$|/search$)",
            collections_filter_path=r"^/collections(/[^/]+)?$",
            root_path="/stac",
        )
        request = Request(request_scope)
        data = {
            "stac_version": "1.0.0",
            "id": "test-catalog",
            "description": "Test catalog",
            "links": [
                {"rel": "self", "href": "https://example.com/stac/"},
                {"rel": "data", "href": "https://example.com/stac/collections"},
                {
                    "rel": "search",
                    "href": "https://example.com/stac/search",
                    "method": "GET",
                },
                {
                    "rel": "items",
                    "href": "https://example.com/stac/collections/foo/items",
                },
            ],
        }

        transformed = middleware.transform_json(data, request)

        self_link = next(link for link in transformed["links"] if link["rel"] == "self")
        assert "auth:refs" not in self_link

        data_link = next(link for link in transformed["links"] if link["rel"] == "data")
        assert "auth:refs" in data_link
        assert "test_auth" in data_link["auth:refs"]

        search_link = next(
            link for link in transformed["links"] if link["rel"] == "search"
        )
        assert "auth:refs" in search_link

        items_link = next(
            link for link in transformed["links"] if link["rel"] == "items"
        )
        assert "auth:refs" in items_link
