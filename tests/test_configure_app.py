"""Tests for configuring an external FastAPI application."""

import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

import stac_auth_proxy.app as app_module
from stac_auth_proxy import Settings, configure_app
from stac_auth_proxy.metrics import classify_operation


def get_flattened_routes(app: FastAPI | APIRouter, prefix=""):
    """
    Recursively extracts all flattened routes from a FastAPI app,
    navigating through Mounts, APIRouters, and FastAPI >= 0.137 _IncludedRouters.

    Code adapted from https://github.com/stac-utils/stac-fastapi-pgstac/blob/a81cc09427a4e33c343f4f41110a3c1dc532aa51/tests/api/test_api.py#L73-L111
    MIT License
    """
    api_routes = set()
    routes = getattr(app, "routes", [])

    for route in routes:
        # 1. Standard Endpoints (APIRoute)
        if hasattr(route, "methods") and route.methods:
            for m in route.methods:
                if m == "HEAD":
                    continue
                r_path = getattr(route, "path", "")
                full_path = f"{prefix}{r_path}".replace("//", "/")
                api_routes.add(full_path)

        # 2. Recurse into Mounts (Starlette)
        if hasattr(route, "app") and hasattr(route.app, "routes"):
            r_path = getattr(route, "path", getattr(route, "prefix", ""))
            next_prefix = f"{prefix}{r_path}"
            api_routes.update(get_flattened_routes(route.app, next_prefix))

        # 3. Recurse into FastAPI >= 0.137 _IncludedRouter wrappers
        if hasattr(route, "original_router"):
            r_prefix = getattr(route, "prefix", "")
            if not r_prefix and hasattr(route, "include_context"):
                r_prefix = getattr(route.include_context, "prefix", "")
            next_prefix = f"{prefix}{r_prefix}"
            api_routes.update(get_flattened_routes(route.original_router, next_prefix))

        # 4. Recurse into classic FastAPI/Starlette Routers (< 0.137)
        elif hasattr(route, "routes") and route is not app:
            r_path = getattr(route, "path", getattr(route, "prefix", ""))
            next_prefix = f"{prefix}{r_path}"
            api_routes.update(get_flattened_routes(route, next_prefix))

    return api_routes


def test_configure_app_excludes_proxy_route():
    """Ensure `configure_app` adds health route and omits proxy route."""
    app = FastAPI()
    settings = Settings(
        upstream_url="https://example.com",
        oidc_discovery_url="https://example.com/.well-known/openid-configuration",
        wait_for_upstream=False,
        check_conformance=False,
        default_public=True,
    )

    configure_app(app, settings)

    routes = get_flattened_routes(app)
    assert settings.healthz_prefix in routes
    assert "/{path:path}" not in routes


def test_metrics_endpoint_returns_prometheus_output():
    """Metrics returns Prometheus exposition format when enabled in PUBLIC_ENDPOINTS."""
    app = FastAPI()
    settings = Settings(
        upstream_url="https://example.com",
        oidc_discovery_url="https://example.com/.well-known/openid-configuration",
        wait_for_upstream=False,
        check_conformance=False,
        default_public=True,
    )

    configure_app(app, settings)
    app.add_api_route("/collections", lambda: {"collections": []}, methods=["GET"])
    client = TestClient(app)
    assert client.get("/collections").status_code == 200
    response = client.get("/_mgmt/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# HELP" in response.text
    assert (
        'http_requests_total{method="GET",operation="list_collections",status="2xx"}'
        in response.text
    )
    assert (
        'http_request_duration_seconds_count{method="GET",operation="list_collections"}'
        in response.text
    )


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("GET", "/", "landing"),
        ("GET", "/conformance", "conformance"),
        ("GET", "/search", "search"),
        ("POST", "/search", "search"),
        ("GET", "/collections", "list_collections"),
        ("POST", "/collections", "create_collection"),
        ("GET", "/collections/sentinel-2", "get_collection"),
        ("PUT", "/collections/sentinel-2", "edit_collection"),
        ("DELETE", "/collections/sentinel-2", "delete_collection"),
        ("GET", "/collections/sentinel-2/items", "list_items"),
        ("POST", "/collections/sentinel-2/items", "create_item"),
        ("GET", "/collections/sentinel-2/items/abc", "get_item"),
        ("DELETE", "/collections/sentinel-2/items/abc", "delete_item"),
        ("POST", "/collections/sentinel-2/bulk_items", "bulk"),
        ("GET", "/unknown", "unknown"),
        ("POST", "/conformance", "unknown"),
    ],
)
def test_classify_operation(method, path, expected):
    """STAC paths map to low-cardinality operation names."""
    assert classify_operation(method, path) == expected


def test_metrics_endpoint_skipped_without_instrumentator(monkeypatch):
    """Metrics route and public endpoint are omitted when the extra is absent."""
    monkeypatch.setattr(app_module, "METRICS_AVAILABLE", False)
    app = FastAPI()
    settings = Settings(
        upstream_url="https://example.com",
        oidc_discovery_url="https://example.com/.well-known/openid-configuration",
        wait_for_upstream=False,
        check_conformance=False,
    )

    configure_app(app, settings)

    assert "/_mgmt/metrics" not in get_flattened_routes(app)
    assert r"^/_mgmt/metrics" not in settings.public_endpoints


def _app_with_own_root_path(proxy_root_path="/stac"):
    """
    Library mode: the STAC app sets root_path itself (as stac-fastapi does from
    ROOT_PATH), with or without the proxy's own ROOT_PATH.
    """
    app = FastAPI(root_path="/stac")
    settings = Settings(
        upstream_url="https://example.com",
        oidc_discovery_url="https://example.com/.well-known/openid-configuration",
        wait_for_upstream=False,
        check_conformance=False,
        default_public=True,
        root_path=proxy_root_path,
        items_filter={
            "cls": "stac_auth_proxy.filters:Template",
            "args": ["collection = 'allowed'"],
        },
    )
    configure_app(app, settings)
    hits = []

    @app.delete("/collections/{collection_id}")
    async def delete_collection(collection_id: str):
        hits.append(("delete", collection_id))
        return {"deleted": collection_id}

    @app.get("/collections/{collection_id}/items/{item_id}")
    async def get_item(collection_id: str, item_id: str):
        hits.append(("get_item", collection_id, item_id))
        return {"type": "Feature", "id": item_id, "collection": collection_id}

    return app, hits


@pytest.mark.parametrize("proxy_root_path", ["/stac", ""])
def test_app_root_path_double_prefix_cannot_skip_auth(proxy_root_path):
    """Neither the root path nor a doubled one reaches a private route without a token."""
    app, hits = _app_with_own_root_path(proxy_root_path)
    client = TestClient(app)

    assert client.delete("/stac/collections/x").status_code == 401
    response = client.delete("/stac/stac/collections/x")
    assert response.status_code == 404
    assert hits == []


@pytest.mark.parametrize("proxy_root_path", ["/stac", ""])
def test_app_root_path_double_prefix_cannot_skip_filter(proxy_root_path):
    """Records under the root path, doubled or not, are filtered."""
    app, hits = _app_with_own_root_path(proxy_root_path)
    client = TestClient(app)

    assert client.get("/stac/collections/allowed/items/i").status_code == 200
    assert client.get("/stac/collections/secret/items/i").status_code == 404
    hits.clear()

    response = client.get("/stac/stac/collections/secret/items/i")
    assert response.status_code == 404
    assert "secret" not in response.text
    assert hits == []


def test_app_root_path_without_proxy_root_path_keeps_mounts_and_urls(tmp_path):
    """
    Removing the app's own root path for the checks (ROOT_PATH unset) must not break
    Mounts, or URLs built from root_path (request.base_url, FastAPI's docs).
    """
    (tmp_path / "a.css").write_text("body {}")
    app, _ = _app_with_own_root_path(proxy_root_path="")
    app.mount("/static", StaticFiles(directory=tmp_path), name="static")

    @app.get("/whoami")
    async def whoami(request: Request):
        return {"base_url": str(request.base_url), "path": request.url.path}

    client = TestClient(app)
    assert client.get("/stac/static/a.css").text == "body {}"
    # Routes see the usual ASGI request (root path included) ...
    assert client.get("/stac/whoami").json() == {
        "base_url": "http://testserver/stac/",
        "path": "/stac/whoami",
    }
    # ... so URLs built from root_path, like FastAPI's docs, keep the prefix
    assert "/stac/openapi.json" in client.get("/stac/docs").text


def test_metrics_classify_routed_path_with_root_path():
    """With ROOT_PATH, operations are classified on the path without it."""
    from prometheus_client import REGISTRY

    app = FastAPI(root_path="/stac")
    configure_app(
        app,
        Settings(
            upstream_url="https://example.com",
            oidc_discovery_url="https://example.com/.well-known/openid-configuration",
            wait_for_upstream=False,
            check_conformance=False,
            default_public=True,
            root_path="/stac",
        ),
    )
    app.add_api_route("/search", lambda: {}, methods=["GET"])
    labels = {"method": "GET", "operation": "search", "status": "2xx"}
    before = REGISTRY.get_sample_value("http_requests_total", labels) or 0
    assert TestClient(app).get("/stac/search").status_code == 200
    assert REGISTRY.get_sample_value("http_requests_total", labels) == before + 1


def test_outer_middleware_sees_routed_endpoint_with_root_path():
    """Keys set while routing (e.g. scope["route"]) reach middleware outside the proxy's."""
    app = FastAPI()
    configure_app(
        app,
        Settings(
            upstream_url="https://example.com",
            oidc_discovery_url="https://example.com/.well-known/openid-configuration",
            wait_for_upstream=False,
            check_conformance=False,
            default_public=True,
            root_path="/stac",
        ),
    )
    app.add_api_route("/collections", lambda: {}, methods=["GET"])
    seen = []

    class Tracing:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)
            if scope["type"] == "http":
                seen.append(scope.get("route"))

    app.add_middleware(Tracing)
    assert TestClient(app).get("/stac/collections").status_code == 200
    assert [route.path for route in seen] == ["/collections"]
