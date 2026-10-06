"""
Path-based policies must match case-insensitively.

Some upstreams (e.g. stac-server, built on Express) route case-insensitively, so
``/Collections/c/items/i`` reaches the same handler as ``/collections/c/items/i``.
Auth, scope and CQL2 filter decisions must therefore not be bypassable by changing
the case of a literal path segment.
"""

import json

import pytest
from cql2 import Expr
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse
from utils import AppFactory, get_upstream_request, single_chunk_async_stream_response

from stac_auth_proxy.middleware.Cql2ValidateTransactionMiddleware import (
    Cql2ValidateTransactionMiddleware,
)
from stac_auth_proxy.utils.requests import extract_variables

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration"
)


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/Collections"),
        ("PUT", "/COLLECTIONS/c"),
        ("DELETE", "/Collections/c"),
        ("POST", "/Collections/c/Items"),
        ("PUT", "/COLLECTIONS/c/ITEMS/i"),
        ("DELETE", "/Collections/c/items/i"),
        ("POST", "/collections/c/BULK_ITEMS"),
    ],
)
def test_private_endpoints_case_insensitive(source_api_server, method, path):
    """Anonymous transactions with a mixed-case path are rejected (default private endpoints)."""
    app = app_factory(upstream_url=source_api_server, default_public=True)
    response = TestClient(app).request(method, path)
    assert response.status_code == 401


def test_private_endpoint_scopes_case_insensitive(source_api_server, token_builder):
    """Required scopes are enforced regardless of path case."""
    app = app_factory(
        upstream_url=source_api_server,
        default_public=False,
        private_endpoints={
            r"^/collections/([^/]+)/items/([^/]+)$": [("DELETE", "write")]
        },
    )
    token = token_builder({"sub": "user", "scope": "read"})
    response = TestClient(app, headers={"Authorization": f"Bearer {token}"}).delete(
        "/Collections/c/Items/i"
    )
    assert response.status_code == 403


def test_public_endpoints_case_sensitive(source_api_server):
    """Public endpoints stay case-sensitive so case variants fail closed."""
    app = app_factory(upstream_url=source_api_server, default_public=False)
    client = TestClient(app)
    assert client.get("/conformance").status_code == 200
    assert client.get("/CONFORMANCE").status_code == 401


def test_extract_variables_case_insensitive():
    """Path params are extracted regardless of path case."""
    assert extract_variables("/Collections/c/ITEMS/i") == {
        "collection_id": "c",
        "item_id": "i",
    }


def _filtered_client(source_api_server):
    app = app_factory(
        upstream_url=source_api_server,
        default_public=True,
        items_filter={
            "cls": "stac_auth_proxy.filters:Template",
            "args": ["{{ \"collection = 'public'\" }}"],
        },
        collections_filter={
            "cls": "stac_auth_proxy.filters:Template",
            "args": ["{{ \"id = 'public'\" }}"],
        },
    )
    return TestClient(app)


@pytest.mark.parametrize("path", ["/Search", "/SEARCH"])
async def test_search_get_filtered_case_insensitive(
    mock_upstream, source_api_server, path
):
    """GET /Search gets the items filter appended."""
    response = _filtered_client(source_api_server).get(path)
    assert response.status_code == 200
    proxied = await get_upstream_request(mock_upstream)
    assert proxied.query_params["filter-lang"] == "cql2-text"
    assert Expr(proxied.query_params["filter"]) == Expr("collection = 'public'")


async def test_search_post_filtered_case_insensitive(mock_upstream, source_api_server):
    """POST /Search gets the items filter applied to the body."""
    response = _filtered_client(source_api_server).post("/Search", json={})
    assert response.status_code == 200
    proxied = await get_upstream_request(mock_upstream)
    assert json.loads(proxied.body)["filter"] == {
        "op": "=",
        "args": [{"property": "collection"}, "public"],
    }


@pytest.mark.parametrize(
    "path,record",
    [
        ("/collections/secret/Items/i", {"id": "i", "collection": "secret"}),
        ("/Collections/secret", {"id": "secret"}),
    ],
)
async def test_single_record_filtered_case_insensitive(
    mock_upstream, source_api_server, path, record
):
    """Single records not matching the filter are hidden regardless of path case."""
    mock_upstream.return_value = single_chunk_async_stream_response(
        json.dumps(record).encode()
    )
    response = _filtered_client(source_api_server).get(path)
    assert response.status_code == 404
    proxied = await get_upstream_request(mock_upstream)
    assert "filter" not in proxied.query_params


@pytest.mark.parametrize(
    "path,filter_expr,body",
    [
        ("/Collections", "id = 'public'", {"id": "secret"}),
        (
            "/Collections/c/Items",
            "collection = 'public'",
            {"id": "i", "collection": "secret"},
        ),
        (
            "/collections/c/BULK_ITEMS",
            "collection = 'public'",
            {"items": {"i": {"id": "i", "collection": "secret"}}},
        ),
    ],
)
def test_transaction_validated_case_insensitive(path, filter_expr, body):
    """Transactions with a mixed-case path are validated against the filter."""
    app = FastAPI()
    app.add_middleware(Cql2ValidateTransactionMiddleware)

    @app.middleware("http")
    async def set_filter(request, call_next):
        request.state.cql2_filter = Expr(filter_expr)
        return await call_next(request)

    @app.post("/{path:path}")
    async def upstream():
        return JSONResponse({})

    response = TestClient(app).post(path, json=body)
    assert response.status_code == 403
