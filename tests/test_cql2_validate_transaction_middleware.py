"""Test Cql2ValidateTransactionMiddleware."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from cql2 import Expr
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.testclient import TestClient

from stac_auth_proxy.handlers import ReverseProxyHandler
from stac_auth_proxy.middleware.Cql2ValidateResponseBodyMiddleware import (
    Cql2ValidateResponseBodyMiddleware,
)
from stac_auth_proxy.middleware.Cql2ValidateTransactionMiddleware import (
    Cql2ValidateTransactionMiddleware,
    UpstreamError,
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

    def _create():
        app = FastAPI()
        app.add_middleware(Cql2ValidateTransactionMiddleware)

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

        @app.post("/collections/{collection_id}/bulk_items")
        async def bulk_create_items(request: Request):
            body = await request.body()
            return json.loads(body) if body else {}

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


def _set_cql2_filter(app, cql2_filter, cql2_read_filter=None):
    """Add middleware that sets cql2_filter (and cql2_read_filter) on request state."""

    @app.middleware("http")
    async def set_filter(request, call_next):
        request.state.cql2_filter = cql2_filter
        if cql2_read_filter is not None:
            request.state.cql2_read_filter = cql2_read_filter
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


class TestBulkCreate:
    """Test bulk item creation validation."""

    def test_all_items_allowed(self, app_with_middleware, cql2_filter):
        """All items match filter, request passes through."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)
        response = client.post(
            "/collections/test/bulk_items",
            json={
                "items": {
                    "item1": {"id": "item1", "collection": "allowed"},
                    "item2": {"id": "item2", "collection": "allowed"},
                }
            },
        )
        assert response.status_code == 200

    def test_some_items_denied(self, app_with_middleware, cql2_filter):
        """Some items fail filter, returns 403 with failed item IDs."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)
        response = client.post(
            "/collections/test/bulk_items",
            json={
                "items": {
                    "item1": {"id": "item1", "collection": "allowed"},
                    "item2": {"id": "item2", "collection": "denied"},
                }
            },
        )
        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "ForbiddenError"
        assert "item2" in body["description"]

    def test_all_items_denied(self, app_with_middleware, cql2_filter):
        """All items fail filter, returns 403."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)
        response = client.post(
            "/collections/test/bulk_items",
            json={
                "items": {
                    "item1": {"id": "item1", "collection": "denied"},
                    "item2": {"id": "item2", "collection": "denied"},
                }
            },
        )
        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "ForbiddenError"
        assert "item1" in body["description"]
        assert "item2" in body["description"]

    def test_no_filter(self, app_with_middleware):
        """Request passes through when no CQL2 filter is set."""
        app = app_with_middleware()
        client = TestClient(app)
        response = client.post(
            "/collections/test/bulk_items",
            json={
                "items": {
                    "item1": {"id": "item1", "collection": "anything"},
                }
            },
        )
        assert response.status_code == 200

    def test_empty_items(self, app_with_middleware, cql2_filter):
        """Empty items dict passes through."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)
        response = client.post(
            "/collections/test/bulk_items",
            json={"items": {}},
        )
        assert response.status_code == 200

    def test_invalid_json(self, app_with_middleware, cql2_filter):
        """Invalid JSON returns 400."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)
        response = client.post(
            "/collections/test/bulk_items",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "ParseError"

    def test_items_not_object(self, app_with_middleware, cql2_filter):
        """Items field that is not a dict returns 400."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)
        response = client.post(
            "/collections/test/bulk_items",
            json={"items": [{"id": "item1", "collection": "allowed"}]},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "ParseError"

    def test_single_create_in_collection_named_like_bulk_items(
        self, app_with_middleware, cql2_filter
    ):
        """A collection id containing 'bulk_items' must not route to the bulk handler."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)
        response = client.post(
            "/collections/bulk_items_2024/items",
            json={"id": "item1", "collection": "denied"},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "ForbiddenError"


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
        """Returns 502 when upstream fetch raises UpstreamError."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter)
        client = TestClient(app)
        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            side_effect=UpstreamError("Connection refused"),
        ):
            response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 502
        assert response.json()["code"] == "UpstreamError"

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
    def test_record_not_found(
        self, app_with_middleware, cql2_filter, method, path, kwargs
    ):
        """Returns 404 when upstream record does not exist."""
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
        assert response.status_code == 404
        assert response.json()["code"] == "NotFoundError"


CALLER_HEADERS = {
    "Authorization": "Bearer caller-token",
    "If-None-Match": "*",
    "Accept-Encoding": "zstd",
}
LEAKED_HEADERS = {"authorization", "if-none-match", "accept-encoding"}


class TestFetchExistingMiddlewareMode:
    """Existing record is fetched in-process from the wrapped STAC API's routes."""

    def _create(self, get_status=200, existing=None):
        seen = []
        app = FastAPI()
        app.add_middleware(Cql2ValidateTransactionMiddleware)
        _set_cql2_filter(app, Expr(ITEM_FILTER))

        # Stand-in for EnforceAuthMiddleware, which sits outside the transaction
        # middleware; the in-process GET must never need to pass through it again.
        @app.middleware("http")
        async def require_auth(request, call_next):
            if "authorization" not in request.headers:
                return JSONResponse({"code": "Unauthorized"}, status_code=401)
            return await call_next(request)

        @app.get("/collections/{collection_id}/items/{item_id}")
        async def get_item(request: Request):
            seen.append(request.headers)
            request.state.set_by_get = True
            if get_status == "raise":
                raise RuntimeError("downstream blew up")
            if get_status == "not-json":
                return PlainTextResponse("not json")
            if get_status != 200:
                return JSONResponse({"code": "Error"}, status_code=get_status)
            return existing or {"id": "item1", "collection": "allowed"}

        @app.put("/collections/{collection_id}/items/{item_id}")
        async def put_item(request: Request):
            return {"state_leaked": hasattr(request.state, "set_by_get")}

        @app.delete("/collections/{collection_id}/items/{item_id}")
        async def delete_item():
            return {"deleted": True}

        return TestClient(app), seen

    @pytest.mark.parametrize("method", ["put", "delete"])
    def test_fetches_without_caller_headers(self, method):
        """The GET reaches the route without auth, conditional, or encoding headers."""
        client, seen = self._create()
        kwargs = (
            {"json": {"id": "item1", "collection": "allowed"}}
            if method == "put"
            else {}
        )
        response = getattr(client, method)(
            "/collections/allowed/items/item1", headers=CALLER_HEADERS, **kwargs
        )
        assert response.status_code == 200
        assert len(seen) == 1
        assert not LEAKED_HEADERS & set(seen[0].keys())

    def test_state_not_shared_with_caller(self):
        """State written during the in-process GET doesn't leak into the real request."""
        client, _ = self._create()
        response = client.put(
            "/collections/allowed/items/item1",
            json={"id": "item1", "collection": "allowed"},
            headers=CALLER_HEADERS,
        )
        assert response.json() == {"state_leaked": False}

    @pytest.mark.parametrize(
        "get_status,existing,expected_status,code",
        [
            pytest.param(
                200,
                {"id": "item1", "collection": "denied"},
                404,
                "NotFoundError",
                id="existing-denied",
            ),
            pytest.param(404, None, 404, "NotFoundError", id="missing"),
            pytest.param(500, None, 502, "UpstreamError", id="downstream-error"),
            pytest.param("raise", None, 502, "UpstreamError", id="downstream-raises"),
            pytest.param("not-json", None, 502, "UpstreamError", id="not-json"),
        ],
    )
    def test_existing_record_outcomes(
        self, get_status, existing, expected_status, code
    ):
        """Status of the in-process GET maps onto the transaction response."""
        client, _ = self._create(get_status=get_status, existing=existing)
        response = client.put(
            "/collections/allowed/items/item1",
            json={"id": "item1", "collection": "allowed"},
            headers=CALLER_HEADERS,
        )
        assert response.status_code == expected_status
        assert response.json()["code"] == code


class TestFetchExistingProxyMode:
    """Existing record is fetched from the upstream via the reverse proxy handler."""

    def _create(self, get_status=200):
        upstream_requests = []

        def upstream(request: httpx.Request):
            upstream_requests.append(request)
            if request.method == "GET":
                if get_status != 200:
                    return httpx.Response(get_status)
                return httpx.Response(
                    200, json={"id": "item1", "collection": "allowed"}
                )
            return httpx.Response(200, json={"ok": True})

        proxy = ReverseProxyHandler(
            upstream="http://upstream",
            client=httpx.AsyncClient(
                transport=httpx.MockTransport(upstream), base_url="http://upstream"
            ),
        )
        app = FastAPI()
        app.add_middleware(Cql2ValidateTransactionMiddleware)
        _set_cql2_filter(app, Expr(ITEM_FILTER))
        app.add_api_route(
            "/{path:path}",
            proxy.proxy_request,
            methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        )
        return TestClient(app), upstream_requests

    def test_put_fetches_then_forwards(self):
        """PUT issues a clean GET to the upstream, then forwards the PUT."""
        client, upstream_requests = self._create()
        response = client.put(
            "/collections/allowed/items/item1",
            json={"id": "item1", "collection": "allowed"},
            headers=CALLER_HEADERS,
        )
        assert response.status_code == 200
        get, put = upstream_requests
        assert (get.method, get.url.path) == (
            "GET",
            "/collections/allowed/items/item1",
        )
        assert not LEAKED_HEADERS & set(get.headers.keys())
        assert get.headers["host"] == "upstream"
        assert put.method == "PUT"
        assert put.headers["authorization"] == "Bearer caller-token"

    def test_upstream_error(self):
        """A failing upstream GET is reported as 502 and the PUT is not forwarded."""
        client, upstream_requests = self._create(get_status=503)
        response = client.put(
            "/collections/allowed/items/item1",
            json={"id": "item1", "collection": "allowed"},
        )
        assert response.status_code == 502
        assert response.json()["code"] == "UpstreamError"
        assert [r.method for r in upstream_requests] == ["GET"]


class TestReadableButNotWritable:
    """A record the caller may read but not modify is refused with 403, not hidden."""

    READ_ALL = {"op": "isNull", "args": [{"property": "no_such_field"}]}
    READ_NONE = {"op": "=", "args": [{"property": "collection"}, "nothing"]}

    @pytest.mark.parametrize(
        "method,kwargs",
        [
            pytest.param(
                "put",
                {"json": {"id": "item1", "collection": "denied"}},
                id="put",
            ),
            pytest.param("patch", {"json": {"properties": {}}}, id="patch"),
            pytest.param("delete", {}, id="delete"),
        ],
    )
    @pytest.mark.parametrize(
        "read_filter,expected_status,error_code",
        [
            pytest.param(READ_ALL, 403, "ForbiddenError", id="readable"),
            pytest.param(READ_NONE, 404, "NotFoundError", id="not-readable"),
            pytest.param(None, 404, "NotFoundError", id="no-read-filter"),
        ],
    )
    def test_existing_record_denied_by_write_filter(
        self,
        app_with_middleware,
        cql2_filter,
        method,
        kwargs,
        read_filter,
        expected_status,
        error_code,
    ):
        """403 if the read filter matches the existing record, else 404."""
        app = app_with_middleware()
        _set_cql2_filter(
            app, cql2_filter, Expr(read_filter) if read_filter is not None else None
        )
        client = TestClient(app)
        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value={"id": "item1", "collection": "denied", "properties": {}},
        ):
            response = getattr(client, method)(
                "/collections/denied/items/item1", **kwargs
            )
        assert response.status_code == expected_status
        assert response.json()["code"] == error_code

    @pytest.mark.parametrize("method", ["put", "delete"])
    def test_read_filter_that_cannot_be_evaluated_is_404(
        self, app_with_middleware, cql2_filter, method
    ):
        """A read filter that raises on the record fails closed: 404, not 500."""
        app = app_with_middleware()
        # `IN` on a list-valued property cannot be reduced to a boolean
        _set_cql2_filter(app, cql2_filter, Expr("tags IN ('a', 'b')"))
        client = TestClient(app)
        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value={"id": "item1", "collection": "denied", "tags": ["a"]},
        ):
            response = getattr(client, method)(
                "/collections/denied/items/item1",
                **({"json": {"id": "item1"}} if method == "put" else {}),
            )
        assert response.status_code == 404
        assert response.json()["code"] == "NotFoundError"

    @pytest.mark.parametrize("method", ["put", "delete"])
    def test_missing_record_is_404_even_when_everything_is_readable(
        self, app_with_middleware, cql2_filter, method
    ):
        """A record that does not exist stays a 404."""
        app = app_with_middleware()
        _set_cql2_filter(app, cql2_filter, Expr(self.READ_ALL))
        client = TestClient(app)
        with patch.object(
            Cql2ValidateTransactionMiddleware,
            "_fetch_existing",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = getattr(client, method)(
                "/collections/denied/items/item1",
                **({"json": {"id": "item1"}} if method == "put" else {}),
            )
        assert response.status_code == 404
        assert response.json()["code"] == "NotFoundError"

    @pytest.mark.parametrize("method", ["put", "patch", "delete"])
    @pytest.mark.parametrize(
        "read_filter,expected_status",
        [
            pytest.param(READ_ALL, 403, id="readable"),
            pytest.param(READ_NONE, 404, id="not-readable"),
            pytest.param(None, 404, id="no-read-filter"),
        ],
    )
    def test_fetched_through_the_response_check(
        self, cql2_filter, method, read_filter, expected_status
    ):
        """
        In the full stack the in-process GET passes Cql2ValidateResponseBodyMiddleware,
        which must read the record with the caller's read filter, not the write filter.
        """
        app = FastAPI()
        app.add_middleware(Cql2ValidateResponseBodyMiddleware)
        app.add_middleware(Cql2ValidateTransactionMiddleware)
        _set_cql2_filter(
            app, cql2_filter, Expr(read_filter) if read_filter is not None else None
        )

        @app.get("/collections/{collection_id}/items/{item_id}")
        async def get_item():
            return {"id": "item1", "collection": "denied", "properties": {}}

        @app.api_route(
            "/collections/{collection_id}/items/{item_id}",
            methods=["PUT", "PATCH", "DELETE"],
        )
        async def change_item():
            return {"changed": True}

        response = TestClient(app).request(
            method.upper(),
            "/collections/denied/items/item1",
            **({} if method == "delete" else {"json": {"properties": {}}}),
        )
        assert response.status_code == expected_status
