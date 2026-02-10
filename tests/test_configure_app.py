"""Tests for configuring an external FastAPI application."""

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from stac_auth_proxy import Settings, configure_app
from stac_auth_proxy.config import _ClassInput


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


def test_missing_colon_separator():
    """Reject class paths without a colon separator."""
    ci = _ClassInput(cls="os.system")
    with pytest.raises(ValueError, match="expected 'module.path:ClassName' format"):
        ci()


def test_disallowed_module_namespace():
    """Reject modules outside the allowed namespace prefixes."""
    ci = _ClassInput(cls="os:system")
    with pytest.raises(ValueError, match="not in the allowed namespaces"):
        ci()


def test_path_traversal():
    """Reject module paths containing '..' traversal."""
    ci = _ClassInput(cls="stac_auth_proxy...config:Settings")
    with pytest.raises(ValueError, match="path traversal or private access"):
        ci()


def test_private_class_access():
    """Reject access to private or dunder class names."""
    ci = _ClassInput(cls="stac_auth_proxy.config:_ClassInput")
    with pytest.raises(ValueError, match="path traversal or private access"):
        ci()


def test_non_callable():
    """Reject resolved attributes that are not callable."""
    ci = _ClassInput(cls="stac_auth_proxy.config:ALLOWED_MODULE_PREFIXES")
    with pytest.raises(TypeError, match="resolved to a non-callable object"):
        ci()


def test_valid_callable():
    """Allow and invoke a valid callable within the permitted namespace."""
    ci = _ClassInput(cls="stac_auth_proxy.config:str2list")
    assert ci() is None
