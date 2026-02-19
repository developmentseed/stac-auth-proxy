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

ITEM_FILTER = {"op": "=", "args": [{"property": "collection"}, "allowed"]}
COLLECTION_FILTER = {"op": "=", "args": [{"property": "id"}, "my-collection"]}


@pytest.fixture
def cql2_filter():
    """Return a CQL2 filter that matches collection = 'allowed'."""
    return Expr(ITEM_FILTER)


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

    @pytest.mark.parametrize(
        "base,override,expected",
        [
            pytest.param({"a": 1}, {"b": 2}, {"a": 1, "b": 2}, id="disjoint-keys"),
            pytest.param({"a": 1}, {"a": 2}, {"a": 2}, id="override-value"),
            pytest.param(
                {"properties": {"name": "old", "count": 1}},
                {"properties": {"name": "new"}},
                {"properties": {"name": "new", "count": 1}},
                id="nested-dict",
            ),
            pytest.param(
                {"a": {"b": {"c": 1, "d": 2}}},
                {"a": {"b": {"c": 3}}},
                {"a": {"b": {"c": 3, "d": 2}}},
                id="deeply-nested",
            ),
            pytest.param(
                {"a": {"nested": True}},
                {"a": "replaced"},
                {"a": "replaced"},
                id="dict-to-non-dict",
            ),
            pytest.param(
                {"a": "string"},
                {"a": {"nested": True}},
                {"a": {"nested": True}},
                id="non-dict-to-dict",
            ),
        ],
    )
    def test_merge(self, base, override, expected):
        """Deep merge produces expected result."""
        assert _deep_merge(base, override) == expected


class TestCreate:
    """Test item and collection creation validation."""

    @pytest.mark.parametrize(
        "path,body,filter_expr,expected_status",
        [
            pytest.param(
                "/collections/test/items",
                {"id": "item1", "collection": "allowed"},
                ITEM_FILTER,
                200,
                id="item-allowed",
            ),
            pytest.param(
                "/collections/test/items",
                {"id": "item1", "collection": "denied"},
                ITEM_FILTER,
                403,
                id="item-denied",
            ),
            pytest.param(
                "/collections",
                {"id": "my-collection", "type": "Collection"},
                COLLECTION_FILTER,
                200,
                id="collection-allowed",
            ),
            pytest.param(
                "/collections",
                {"id": "denied-collection", "type": "Collection"},
                COLLECTION_FILTER,
                403,
                id="collection-denied",
            ),
        ],
    )
    def test_create(
        self, app_with_middleware, path, body, filter_expr, expected_status
    ):
        """Allow or deny creation based on whether body matches filter."""
        app = app_with_middleware()
        _set_cql2_filter(app, Expr(filter_expr))
        client = TestClient(app)
        response = client.post(path, json=body)
        assert response.status_code == expected_status
        if expected_status == 403:
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


class TestUpdate:
    """Test item and collection update validation."""

    @pytest.mark.parametrize(
        "path,existing,body,filter_expr,expected_status,error_code",
        [
            pytest.param(
                "/collections/allowed/items/item1",
                {"id": "item1", "collection": "allowed", "properties": {"name": "old"}},
                {"id": "item1", "collection": "allowed", "properties": {"name": "new"}},
                ITEM_FILTER,
                200,
                None,
                id="item-allowed",
            ),
            pytest.param(
                "/collections/denied/items/item1",
                {"id": "item1", "collection": "denied", "properties": {}},
                {"id": "item1", "collection": "allowed"},
                ITEM_FILTER,
                404,
                "NotFoundError",
                id="item-existing-not-found",
            ),
            pytest.param(
                "/collections/allowed/items/item1",
                {"id": "item1", "collection": "allowed", "properties": {}},
                {"id": "item1", "collection": "denied", "properties": {}},
                ITEM_FILTER,
                403,
                "ForbiddenError",
                id="item-result-denied",
            ),
            pytest.param(
                "/collections/my-collection",
                {"id": "my-collection", "type": "Collection"},
                {"id": "my-collection", "type": "Collection", "title": "Updated"},
                COLLECTION_FILTER,
                200,
                None,
                id="collection-allowed",
            ),
        ],
    )
    def test_put(
        self,
        app_with_middleware,
        path,
        existing,
        body,
        filter_expr,
        expected_status,
        error_code,
    ):
        """PUT validates both existing record and new body against filter."""
        app = app_with_middleware()
        _set_cql2_filter(app, Expr(filter_expr))
        client = TestClient(app)
        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            response = client.put(path, json=body)
        assert response.status_code == expected_status
        if error_code:
            assert response.json()["code"] == error_code

    @pytest.mark.parametrize(
        "existing,body,expected_status",
        [
            pytest.param(
                {"id": "item1", "collection": "allowed", "properties": {"name": "old"}},
                {"properties": {"name": "new"}},
                200,
                id="allowed",
            ),
            pytest.param(
                {
                    "id": "item1",
                    "collection": "allowed",
                    "properties": {"name": "old", "count": 5},
                    "assets": {"thumbnail": {"href": "http://example.com/thumb.png"}},
                },
                {"properties": {"name": "new"}},
                200,
                id="merge-preserves-collection",
            ),
            pytest.param(
                {"id": "item1", "collection": "allowed", "properties": {}},
                {"collection": "denied"},
                403,
                id="changes-collection-denied",
            ),
        ],
    )
    def test_patch(
        self, app_with_middleware, cql2_filter, existing, body, expected_status
    ):
        """PATCH merges body with existing record and validates the result."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)
        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            response = client.patch("/collections/allowed/items/item1", json=body)
        assert response.status_code == expected_status
        if expected_status == 403:
            assert response.json()["code"] == "ForbiddenError"


class TestDelete:
    """Test item and collection deletion validation."""

    @pytest.mark.parametrize(
        "path,existing,filter_expr,expected_status,error_code",
        [
            pytest.param(
                "/collections/allowed/items/item1",
                {"id": "item1", "collection": "allowed"},
                ITEM_FILTER,
                200,
                None,
                id="item-allowed",
            ),
            pytest.param(
                "/collections/denied/items/item1",
                {"id": "item1", "collection": "denied"},
                ITEM_FILTER,
                404,
                "NotFoundError",
                id="item-denied",
            ),
            pytest.param(
                "/collections/my-collection",
                {"id": "my-collection", "type": "Collection"},
                COLLECTION_FILTER,
                200,
                None,
                id="collection-allowed",
            ),
            pytest.param(
                "/collections/other-collection",
                {"id": "other-collection", "type": "Collection"},
                COLLECTION_FILTER,
                404,
                "NotFoundError",
                id="collection-denied",
            ),
        ],
    )
    def test_delete(
        self,
        app_with_middleware,
        path,
        existing,
        filter_expr,
        expected_status,
        error_code,
    ):
        """Delete validates existing record against filter."""
        app = app_with_middleware()
        _set_cql2_filter(app, Expr(filter_expr))
        client = TestClient(app)
        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            response = client.delete(path)
        assert response.status_code == expected_status
        if error_code:
            assert response.json()["code"] == error_code


class TestPassthrough:
    """Test that non-transaction requests pass through unmodified."""

    @pytest.mark.parametrize(
        "method,path,kwargs",
        [
            pytest.param("get", "/collections/test/items/item1", {}, id="get-item"),
            pytest.param(
                "post", "/search", {"json": {"collections": ["test"]}}, id="post-search"
            ),
            pytest.param("get", "/search", {}, id="get-search"),
        ],
    )
    def test_passthrough(self, app_with_middleware, cql2_filter, method, path, kwargs):
        """Non-transaction requests pass through without validation."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 200


class TestUpstreamFetchFailure:
    """Test behavior when upstream is unreachable."""

    @pytest.mark.parametrize(
        "method,path,kwargs",
        [
            pytest.param(
                "put",
                "/collections/allowed/items/item1",
                {"json": {"id": "item1", "collection": "allowed"}},
                id="put",
            ),
            pytest.param("delete", "/collections/allowed/items/item1", {}, id="delete"),
        ],
    )
    def test_upstream_unreachable(
        self, app_with_middleware, cql2_filter, method, path, kwargs
    ):
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
            response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 502
