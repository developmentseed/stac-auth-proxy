"""Tests for configuring an external FastAPI application."""

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from stac_auth_proxy import Settings, configure_app


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
    )

    configure_app(app, settings)
    response = TestClient(app).get("/_mgmt/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# HELP" in response.text
