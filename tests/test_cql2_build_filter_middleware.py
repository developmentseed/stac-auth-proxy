"""Test Cql2BuildFilterMiddleware."""

from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from stac_auth_proxy.middleware.Cql2BuildFilterMiddleware import (
    Cql2BuildFilterMiddleware,
)


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
