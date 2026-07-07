"""Tests for optional Prometheus metrics support."""

import builtins

import pytest
from fastapi.testclient import TestClient
from test_configure_app import get_flattened_routes
from utils import AppFactory

from stac_auth_proxy import Settings, create_app

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
)


def test_metrics_disabled_by_default(source_api_server):
    """The metrics endpoint is not registered unless explicitly enabled."""
    app = app_factory(upstream_url=source_api_server)

    assert "/metrics" not in get_flattened_routes(app)


def test_metrics_enabled_from_env(monkeypatch, source_api_server):
    """ENABLE_METRICS=true exposes Prometheus text output."""
    monkeypatch.setenv("ENABLE_METRICS", "true")
    settings = Settings(
        upstream_url=source_api_server,
        oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
        wait_for_upstream=False,
        check_conformance=False,
    )
    app = create_app(settings)
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# HELP" in response.text


def test_metrics_enabled_without_extra_fails(monkeypatch, source_api_server):
    """Enabling metrics without the optional dependency fails clearly."""
    real_import = builtins.__import__

    def raise_for_instrumentator(name, *args, **kwargs):
        if name == "prometheus_fastapi_instrumentator":
            raise ImportError("No module named prometheus_fastapi_instrumentator")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", raise_for_instrumentator)
    settings = Settings(
        upstream_url=source_api_server,
        oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
        enable_metrics=True,
        wait_for_upstream=False,
        check_conformance=False,
    )

    with pytest.raises(RuntimeError, match=r"Install stac-auth-proxy\[metrics\]"):
        create_app(settings)
