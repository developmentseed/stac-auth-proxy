"""Test Cql2BuildFilterMiddleware."""

import pytest
from fastapi import FastAPI, HTTPException, Request
from starlette.testclient import TestClient

from stac_auth_proxy.middleware.Cql2BuildFilterMiddleware import (
    Cql2BuildFilterMiddleware,
)

# Example filter path configs from docs/user-guide/configuration.md
AGGREGATION_COLLECTIONS_FILTER_PATH = [
    r"^/collections(?:/(?P<collection_id>[^/]+))?$",
    r"^/collections/(?P<collection_id>[^/]+)/aggregate$",
    r"^/collections/(?P<collection_id>[^/]+)/aggregations$",
]

AGGREGATION_ITEMS_FILTER_PATH = [
    r"^(?:/collections/(?P<collection_id>[^/]+)/items(?:/(?P<item_id>[^/]+))?|/search)$",
    r"^/aggregate$",
    r"^/aggregations$",
]


def build_middleware(**kwargs) -> Cql2BuildFilterMiddleware:
    """Build the filter middleware with a no-op filter."""
    kwargs.setdefault("collections_filter", lambda ctx: "true")
    kwargs.setdefault("items_filter", lambda ctx: "true")
    return Cql2BuildFilterMiddleware(app=None, **kwargs)


class TestOptionsRequest:
    """Test middleware behavior with OPTIONS requests."""

    def test_options_request_skips_filter_building(self):
        """Test that OPTIONS requests skip CQL2 filter building."""
        app = FastAPI()

        # Create a simple filter that would be applied to items
        async def items_filter(context):
            return "private = false"

        # Add middleware with a filter
        app.add_middleware(
            Cql2BuildFilterMiddleware,
            items_filter=items_filter,
        )

        @app.options("/search")
        async def search_options(request: Request):
            # Check if the filter was built and added to request state
            cql2_filter = getattr(request.state, "cql2_filter", None)
            return {
                "filter_was_built": cql2_filter is not None,
                "methods": ["GET", "POST", "OPTIONS"],
            }

        @app.get("/search")
        async def search_get(request: Request):
            # Check if the filter was built for comparison
            cql2_filter = getattr(request.state, "cql2_filter", None)
            return {
                "filter_was_built": cql2_filter is not None,
            }

        client = TestClient(app)

        # Test OPTIONS request - filter should NOT be built
        options_response = client.options("/search")
        assert options_response.status_code == 200
        options_data = options_response.json()
        assert options_data["filter_was_built"] is False

        # Test GET request - filter SHOULD be built
        get_response = client.get("/search")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["filter_was_built"] is True

    def test_options_request_on_items_endpoint(self):
        """Test that OPTIONS requests skip filter building on items endpoint."""
        app = FastAPI()

        async def items_filter(context):
            return "collection = 'test'"

        app.add_middleware(
            Cql2BuildFilterMiddleware,
            items_filter=items_filter,
        )

        @app.options("/collections/test-collection/items")
        async def items_options(request: Request):
            cql2_filter = getattr(request.state, "cql2_filter", None)
            return {"filter_was_built": cql2_filter is not None}

        @app.get("/collections/test-collection/items")
        async def items_get(request: Request):
            cql2_filter = getattr(request.state, "cql2_filter", None)
            return {"filter_was_built": cql2_filter is not None}

        client = TestClient(app)

        # Test OPTIONS request on items endpoint
        options_response = client.options("/collections/test-collection/items")
        assert options_response.status_code == 200
        assert options_response.json()["filter_was_built"] is False

        # Test GET request on items endpoint for comparison
        get_response = client.get("/collections/test-collection/items")
        assert get_response.status_code == 200
        assert get_response.json()["filter_was_built"] is True


class TestErrorHandling:
    """Test middleware behavior when filter_fcn returns an exception."""

    def test_exception_handling(self):
        """Test that the middleware correctly handles exceptions raised by the filter function."""
        app = FastAPI()

        # Create a simple filter, function raise an exception if user is not "good"
        async def items_filter(context):
            query_params = context["req"].get("query_params", {})
            if query_params.get("user") != "good":
                raise HTTPException(status_code=403, detail="Bad user")

            return "private = false"

        # Add middleware with a filter
        app.add_middleware(
            Cql2BuildFilterMiddleware,
            items_filter=items_filter,
        )

        @app.get("/search")
        async def search_get(request: Request):
            return {}

        client = TestClient(app)

        # Test GET request SHOULD return 403 for bad user
        get_response = client.get("/search")
        assert get_response.status_code == 403

        # Test GET request SHOULD return 200 for good user
        get_response = client.get("/search", params={"user": "good"})
        assert get_response.status_code == 200


class TestFilterPathParams:
    """Test extraction of path params from the configured filter paths."""

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/collections/123", {"collection_id": "123"}),
            ("/collections/123/items", {"collection_id": "123"}),
            ("/collections/123/items/456", {"collection_id": "123", "item_id": "456"}),
            ("/search", {}),
        ],
    )
    def test_default_patterns_reproduce_the_builtin_extraction(self, path, expected):
        """The defaults yield exactly what the built-in extractor yielded."""
        mw = build_middleware()
        _, path_params = mw._get_filter(path)
        assert path_params == expected

    def test_a_pattern_extracts_its_own_named_groups(self):
        """A custom endpoint gets whatever params its own pattern declares."""
        mw = build_middleware(
            collections_filter_path=r"^/mosaic/(?P<zoom>[^/]+)/(?P<x>[^/]+)/(?P<y>[^/]+)/(?P<collection_id>[^/]+)\.png$"
        )
        filter_builder, path_params = mw._get_filter(
            "/mosaic/8/12/34/my-collection.png"
        )

        assert filter_builder is not None
        assert path_params == {
            "zoom": "8",
            "x": "12",
            "y": "34",
            "collection_id": "my-collection",
        }

    @pytest.mark.parametrize(
        "path", ["/collections/123/queryables", "/collections/123/bulk_items"]
    )
    def test_defaults_route_no_filter_to_queryables_or_bulk_items(self, path):
        """The defaults leave these paths alone, so no filter and no params."""
        mw = build_middleware()
        assert mw._get_filter(path) == (None, {})

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/collections/123/queryables", {"collection_id": "123"}),
            ("/collections/123/bulk_items", {"collection_id": "123"}),
        ],
    )
    def test_routing_a_path_in_without_named_groups_uses_builtin_extraction(
        self, path, expected
    ):
        """Widening the pattern is enough; the built-in extractor supplies the params."""
        mw = build_middleware(
            collections_filter_path=r"^/collections/[^/]+/(queryables|bulk_items)$",
        )
        assert mw._get_filter(path)[1] == expected

    def test_a_non_participating_alternative_does_not_leak_nulls(self):
        """Groups in an unmatched alternative are dropped, not passed as None."""
        mw = build_middleware(
            collections_filter_path=[r"^(?:/a/(?P<x>\d+)|/b/(?P<y>\d+))$"],
        )
        assert mw._get_filter("/b/7")[1] == {"y": "7"}

    def test_a_pattern_without_named_groups_falls_back_to_builtin_extraction(self):
        """A pre-existing config keeps the params it has always received."""
        mw = build_middleware(items_filter_path=r"^/collections/([^/]+)/items$")
        assert mw._get_filter("/collections/abc/items")[1] == {"collection_id": "abc"}

    def test_a_string_is_normalized_when_constructed_directly(self):
        """Middleware constructed with a string keeps working."""
        mw = build_middleware(items_filter_path=r"^/collections/([^/]+)/items$")
        assert mw.items_filter_path == [r"^/collections/([^/]+)/items$"]

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/collections/123/aggregate", {"collection_id": "123"}),
            ("/collections/123/aggregations", {"collection_id": "123"}),
            ("/collections/123", {"collection_id": "123"}),
            ("/collections/123/items", {"collection_id": "123"}),
            ("/aggregate", {}),
            ("/aggregations", {}),
            ("/search", {}),
        ],
    )
    def test_the_documented_aggregation_config_covers_every_endpoint(
        self, path, expected
    ):
        """The Aggregation extension example in the docs works as written."""
        mw = build_middleware(
            collections_filter_path=AGGREGATION_COLLECTIONS_FILTER_PATH,
            items_filter_path=AGGREGATION_ITEMS_FILTER_PATH,
        )
        filter_builder, path_params = mw._get_filter(path)

        assert filter_builder is not None
        assert path_params == expected
