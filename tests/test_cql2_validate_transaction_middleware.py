"""Test Cql2ValidateTransactionMiddleware."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from cql2 import Expr
from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from stac_auth_proxy.middleware.Cql2ValidateTransactionMiddleware import (
    Cql2ValidateTransactionMiddleware,
    _deep_merge,
)


@pytest.fixture
def cql2_filter():
    """Return a CQL2 filter that matches collection = 'allowed'."""
    return Expr({"op": "=", "args": [{"property": "collection"}, "allowed"]})


@pytest.fixture
def app_with_middleware():
    """Create a FastAPI app with the transaction middleware."""

    def _create(upstream_url="http://upstream:8080"):
        app = FastAPI()
        app.add_middleware(
            Cql2ValidateTransactionMiddleware,
            upstream_url=upstream_url,
        )

        @app.post("/collections/{collection_id}/items")
        async def create_item(request: Request):
            body = await request.body()
            return json.loads(body) if body else {}

        @app.put("/collections/{collection_id}/items/{item_id}")
        async def update_item_put(request: Request):
            body = await request.body()
            return json.loads(body) if body else {}

        @app.patch("/collections/{collection_id}/items/{item_id}")
        async def update_item_patch(request: Request):
            body = await request.body()
            return json.loads(body) if body else {}

        @app.delete("/collections/{collection_id}/items/{item_id}")
        async def delete_item(request: Request):
            return {"deleted": True}

        @app.post("/collections")
        async def create_collection(request: Request):
            body = await request.body()
            return json.loads(body) if body else {}

        @app.put("/collections/{collection_id}")
        async def update_collection_put(request: Request):
            body = await request.body()
            return json.loads(body) if body else {}

        @app.patch("/collections/{collection_id}")
        async def update_collection_patch(request: Request):
            body = await request.body()
            return json.loads(body) if body else {}

        @app.delete("/collections/{collection_id}")
        async def delete_collection(request: Request):
            return {"deleted": True}

        @app.get("/search")
        async def search_get(request: Request):
            return {"type": "FeatureCollection", "features": []}

        @app.post("/search")
        async def search_post(request: Request):
            return {"type": "FeatureCollection", "features": []}

        @app.get("/collections/{collection_id}/items/{item_id}")
        async def get_item(request: Request):
            return {"id": "item1", "collection": "allowed"}

        return app

    return _create


def _set_cql2_filter(app, cql2_filter):
    """Add middleware that sets cql2_filter on request state."""

    @app.middleware("http")
    async def set_filter(request, call_next):
        request.state.cql2_filter = cql2_filter
        return await call_next(request)


class TestDeepMerge:
    """Test the _deep_merge utility function."""

    def test_simple_merge(self):
        """Merge two dicts with disjoint keys."""
        assert _deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_override_value(self):
        """Override replaces base value for same key."""
        assert _deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_nested_dict_merge(self):
        """Merge nested dicts recursively."""
        base = {"properties": {"name": "old", "count": 1}}
        override = {"properties": {"name": "new"}}
        result = _deep_merge(base, override)
        assert result == {"properties": {"name": "new", "count": 1}}

    def test_deeply_nested_merge(self):
        """Merge deeply nested dicts recursively."""
        base = {"a": {"b": {"c": 1, "d": 2}}}
        override = {"a": {"b": {"c": 3}}}
        result = _deep_merge(base, override)
        assert result == {"a": {"b": {"c": 3, "d": 2}}}

    def test_override_dict_with_non_dict(self):
        """Replace a nested dict with a non-dict value."""
        base = {"a": {"nested": True}}
        override = {"a": "replaced"}
        result = _deep_merge(base, override)
        assert result == {"a": "replaced"}

    def test_override_non_dict_with_dict(self):
        """Replace a non-dict value with a nested dict."""
        base = {"a": "string"}
        override = {"a": {"nested": True}}
        result = _deep_merge(base, override)
        assert result == {"a": {"nested": True}}


class TestCreateItem:
    """Test item creation validation."""

    def test_create_allowed(self, app_with_middleware, cql2_filter):
        """Allow item creation when body matches filter."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        response = client.post(
            "/collections/test/items",
            json={"id": "item1", "collection": "allowed"},
        )
        assert response.status_code == 200
        assert response.json()["collection"] == "allowed"

    def test_create_denied(self, app_with_middleware, cql2_filter):
        """Deny item creation when body doesn't match filter."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        response = client.post(
            "/collections/test/items",
            json={"id": "item1", "collection": "denied"},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "ForbiddenError"

    def test_create_no_filter(self, app_with_middleware):
        """Request passes through when no CQL2 filter is set."""
        app = app_with_middleware()
        client = TestClient(app)

        response = client.post(
            "/collections/test/items",
            json={"id": "item1", "collection": "anything"},
        )
        assert response.status_code == 200


class TestCreateCollection:
    """Test collection creation validation."""

    def test_create_collection_allowed(self, app_with_middleware):
        """Collection filter uses 'id' property for collections."""
        cql2_filter = Expr(
            {"op": "=", "args": [{"property": "id"}, "allowed-collection"]}
        )
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        response = client.post(
            "/collections",
            json={"id": "allowed-collection", "type": "Collection"},
        )
        assert response.status_code == 200

    def test_create_collection_denied(self, app_with_middleware):
        """Deny collection creation when body doesn't match filter."""
        cql2_filter = Expr(
            {"op": "=", "args": [{"property": "id"}, "allowed-collection"]}
        )
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        response = client.post(
            "/collections",
            json={"id": "denied-collection", "type": "Collection"},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "ForbiddenError"


class TestUpdateItem:
    """Test item update validation."""

    def test_put_allowed(self, app_with_middleware, cql2_filter):
        """Allow PUT when existing and new body both match filter."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        existing = {
            "id": "item1",
            "collection": "allowed",
            "properties": {"name": "old"},
        }
        new_body = {
            "id": "item1",
            "collection": "allowed",
            "properties": {"name": "new"},
        }

        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            response = client.put(
                "/collections/allowed/items/item1",
                json=new_body,
            )
        assert response.status_code == 200
        assert response.json()["properties"]["name"] == "new"

    def test_put_existing_not_found(self, app_with_middleware, cql2_filter):
        """Existing record doesn't match filter → 404."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        existing = {"id": "item1", "collection": "denied", "properties": {}}

        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            response = client.put(
                "/collections/denied/items/item1",
                json={"id": "item1", "collection": "allowed"},
            )
        assert response.status_code == 404
        assert response.json()["code"] == "NotFoundError"

    def test_put_result_denied(self, app_with_middleware, cql2_filter):
        """Existing matches, but new body doesn't → 403."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        existing = {"id": "item1", "collection": "allowed", "properties": {}}
        new_body = {"id": "item1", "collection": "denied", "properties": {}}

        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            response = client.put(
                "/collections/allowed/items/item1",
                json=new_body,
            )
        assert response.status_code == 403
        assert response.json()["code"] == "ForbiddenError"

    def test_patch_allowed(self, app_with_middleware, cql2_filter):
        """Allow PATCH when existing and merged result both match filter."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        existing = {
            "id": "item1",
            "collection": "allowed",
            "properties": {"name": "old"},
        }
        patch_body = {"properties": {"name": "new"}}

        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            response = client.patch(
                "/collections/allowed/items/item1",
                json=patch_body,
            )
        assert response.status_code == 200

    def test_patch_merge_logic(self, app_with_middleware, cql2_filter):
        """PATCH merges existing + update, validates the merged result."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        existing = {
            "id": "item1",
            "collection": "allowed",
            "properties": {"name": "old", "count": 5},
            "assets": {"thumbnail": {"href": "http://example.com/thumb.png"}},
        }
        # PATCH only updates properties.name, leaves collection intact
        patch_body = {"properties": {"name": "new"}}

        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            response = client.patch(
                "/collections/allowed/items/item1",
                json=patch_body,
            )
        # Should pass because merged result still has collection=allowed
        assert response.status_code == 200

    def test_patch_changes_collection_denied(self, app_with_middleware, cql2_filter):
        """PATCH that changes collection to non-allowed value → 403."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        existing = {"id": "item1", "collection": "allowed", "properties": {}}
        patch_body = {"collection": "denied"}

        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            response = client.patch(
                "/collections/allowed/items/item1",
                json=patch_body,
            )
        assert response.status_code == 403
        assert response.json()["code"] == "ForbiddenError"


class TestDeleteItem:
    """Test item deletion validation."""

    def test_delete_allowed(self, app_with_middleware, cql2_filter):
        """Allow delete when existing record matches filter."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        existing = {"id": "item1", "collection": "allowed"}

        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            response = client.delete("/collections/allowed/items/item1")
        assert response.status_code == 200
        assert response.json()["deleted"] is True

    def test_delete_denied(self, app_with_middleware, cql2_filter):
        """Existing doesn't match filter → 404."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        existing = {"id": "item1", "collection": "denied"}

        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            response = client.delete("/collections/denied/items/item1")
        assert response.status_code == 404
        assert response.json()["code"] == "NotFoundError"


class TestPassthrough:
    """Test that non-transaction requests pass through unmodified."""

    def test_get_passthrough(self, app_with_middleware, cql2_filter):
        """Pass through GET requests without validation."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        response = client.get("/collections/test/items/item1")
        assert response.status_code == 200

    def test_search_post_passthrough(self, app_with_middleware, cql2_filter):
        """Pass through POST /search without validation."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        response = client.post("/search", json={"collections": ["test"]})
        assert response.status_code == 200

    def test_search_get_passthrough(self, app_with_middleware, cql2_filter):
        """Pass through GET /search without validation."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        response = client.get("/search")
        assert response.status_code == 200


class TestUpstreamFetchFailure:
    """Test behavior when upstream is unreachable."""

    def test_update_upstream_unreachable(self, app_with_middleware, cql2_filter):
        """Returns 502 when upstream fetch returns None."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = client.put(
                "/collections/allowed/items/item1",
                json={"id": "item1", "collection": "allowed"},
            )
        assert response.status_code == 502

    def test_delete_upstream_unreachable(self, app_with_middleware, cql2_filter):
        """Returns 502 when upstream fetch returns None."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = client.delete("/collections/allowed/items/item1")
        assert response.status_code == 502


class TestCollectionOperations:
    """Test collection-level transaction operations."""

    def test_update_collection_put_allowed(self, app_with_middleware):
        """Allow PUT on collection when existing and new body match filter."""
        cql2_filter = Expr({"op": "=", "args": [{"property": "id"}, "my-collection"]})
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        existing = {"id": "my-collection", "type": "Collection"}
        new_body = {"id": "my-collection", "type": "Collection", "title": "Updated"}

        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            response = client.put("/collections/my-collection", json=new_body)
        assert response.status_code == 200

    def test_delete_collection_allowed(self, app_with_middleware):
        """Allow collection delete when existing record matches filter."""
        cql2_filter = Expr({"op": "=", "args": [{"property": "id"}, "my-collection"]})
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        existing = {"id": "my-collection", "type": "Collection"}

        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            response = client.delete("/collections/my-collection")
        assert response.status_code == 200

    def test_delete_collection_denied(self, app_with_middleware):
        """Deny collection delete when existing record doesn't match filter."""
        cql2_filter = Expr({"op": "=", "args": [{"property": "id"}, "my-collection"]})
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)

        existing = {"id": "other-collection", "type": "Collection"}

        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            response = client.delete("/collections/other-collection")
        assert response.status_code == 404
