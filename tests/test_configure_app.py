"""Tests for configuring an external FastAPI application."""

from fastapi import FastAPI
from fastapi.routing import APIRoute

from stac_auth_proxy import Settings, configure_app


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

    routes = [r.path for r in app.router.routes if isinstance(r, APIRoute)]
    assert settings.healthz_prefix in routes
    assert "/{path:path}" not in routes
