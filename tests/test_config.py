"""Test config classes."""

import pytest

from stac_auth_proxy.config import CorsSettings, Settings


def test_settings_model_config():
    """Test that the model config is set correctly."""
    settings = Settings(
        upstream_url="https://example.com",
        oidc_discovery_url="https://example.com/.well-known/openid-configuration",
        oidc_discovery_internal_url="https://example2.com/.well-known/openid-configuration",
    )
    assert (
        str(settings.oidc_discovery_internal_url)
        == "https://example2.com/.well-known/openid-configuration"
    )

    settings = Settings(
        upstream_url="https://example.com",
        oidc_discovery_url="https://example.com/.well-known/openid-configuration",
    )
    assert (
        str(settings.oidc_discovery_internal_url)
        == "https://example.com/.well-known/openid-configuration"
    )

    settings = Settings(
        upstream_url="https://example.com",
        oidc_discovery_url="https://example.com/.well-known/openid-configuration",
        allowed_jwt_audiences=["sfeos", "account"],
    )
    assert settings.allowed_jwt_audiences == ["sfeos", "account"]

    settings = Settings(
        upstream_url="https://example.com",
        oidc_discovery_url="https://example.com/.well-known/openid-configuration",
        allowed_jwt_audiences='["sfeos", "account"]',
    )
    assert settings.allowed_jwt_audiences == ["sfeos", "account"]

    settings = Settings(
        upstream_url="https://example.com",
        oidc_discovery_url="https://example.com/.well-known/openid-configuration",
        allowed_jwt_audiences="sfeos,account",
    )
    assert settings.allowed_jwt_audiences == ["sfeos", "account"]

    settings = Settings(
        upstream_url="https://example.com",
        oidc_discovery_url="https://example.com/.well-known/openid-configuration",
        allowed_jwt_audiences="",
    )
    assert settings.allowed_jwt_audiences == [""]


def test_root_path_skip_prefixes():
    """Test parsing and normalization of root_path_skip_prefixes."""
    common_kwargs = {
        "upstream_url": "https://example.com",
        "oidc_discovery_url": "https://example.com/.well-known/openid-configuration",
    }

    # Defaults to empty (feature disabled)
    settings = Settings(**common_kwargs)
    assert list(settings.root_path_skip_prefixes) == []

    # Comma-separated string, with trailing slashes normalized
    settings = Settings(
        **common_kwargs,
        root_path_skip_prefixes="/raster/,/vector,/browser",
    )
    assert list(settings.root_path_skip_prefixes) == ["/raster", "/vector", "/browser"]

    # List input
    settings = Settings(**common_kwargs, root_path_skip_prefixes=["/raster"])
    assert list(settings.root_path_skip_prefixes) == ["/raster"]

    # Empty entries are dropped
    settings = Settings(**common_kwargs, root_path_skip_prefixes="/raster,,")
    assert list(settings.root_path_skip_prefixes) == ["/raster"]

    # Prefixes must start with a slash
    with pytest.raises(ValueError):
        Settings(**common_kwargs, root_path_skip_prefixes="raster")

    # A bare "/" would mean "skip everything" — reject it
    with pytest.raises(ValueError):
        Settings(**common_kwargs, root_path_skip_prefixes="/")


def test_root_path_skip_prefixes_from_environment(monkeypatch):
    """Comma-separated env value (e.g. /raster,/vector) must load as a list."""
    monkeypatch.setenv("UPSTREAM_URL", "https://example.com")
    monkeypatch.setenv(
        "OIDC_DISCOVERY_URL", "https://example.com/.well-known/openid-configuration"
    )
    monkeypatch.setenv("ROOT_PATH_SKIP_PREFIXES", "/raster,/vector,/browser")

    settings = Settings()
    assert list(settings.root_path_skip_prefixes) == ["/raster", "/vector", "/browser"]


def test_settings_model_config_with_environment_variables(monkeypatch):
    """Test that the model config is set correctly with environment variables."""
    monkeypatch.setenv("UPSTREAM_URL", "https://example.com")
    monkeypatch.setenv(
        "OIDC_DISCOVERY_URL", "https://example.com/.well-known/openid-configuration"
    )
    monkeypatch.setenv("ALLOWED_JWT_AUDIENCES", "sfeos,account")

    settings = Settings()
    assert (
        str(settings.oidc_discovery_internal_url)
        == "https://example.com/.well-known/openid-configuration"
    )
    assert settings.allowed_jwt_audiences == ["sfeos", "account"]

    monkeypatch.setenv("ALLOWED_JWT_AUDIENCES", '["user", "account"]')
    settings = Settings()
    assert (
        str(settings.oidc_discovery_internal_url)
        == "https://example.com/.well-known/openid-configuration"
    )
    assert settings.allowed_jwt_audiences == ["user", "account"]


def test_cors_model_config():
    """Test that the CORS model config is set correctly."""
    cors_settings = CorsSettings(
        allow_origins=["https://example.com", "https://example2.com"],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    assert cors_settings.allow_origins == [
        "https://example.com",
        "https://example2.com",
    ]
    assert cors_settings.allow_methods == ["GET", "POST"]
    assert cors_settings.allow_headers == ["Authorization", "Content-Type"]

    cors_settings = CorsSettings(
        allow_origins="https://example.com,https://example2.com",
        allow_methods="GET,POST",
        allow_headers="Authorization,Content-Type",
    )
    assert cors_settings.allow_origins == [
        "https://example.com",
        "https://example2.com",
    ]
    assert cors_settings.allow_methods == ["GET", "POST"]
    assert cors_settings.allow_headers == ["Authorization", "Content-Type"]


def test_items_and_collections_path_parameters():
    """Tests related to parsing Collections/Items regexes from inputs."""
    common_kwargs = {
        "upstream_url": "https://example.com",
        "oidc_discovery_url": "https://example.com/.well-known/openid-configuration",
    }

    # Single pattern case
    settings = Settings(
        **common_kwargs,
        items_filter_path=r"^/collections/([^/]+)/items$",
    )
    assert settings.items_filter_path == [r"^/collections/([^/]+)/items$"]

    # Don't split on commas (valid regex)
    settings = Settings(
        **common_kwargs,
        items_filter_path=r"^/collections/([^/]{2,64})/items$",
    )
    assert settings.items_filter_path == [r"^/collections/([^/]{2,64})/items$"]

    # JSON array decoded into list[str]
    settings = Settings(
        **common_kwargs,
        collections_filter_path='["^/a$", "^/b$"]',
    )
    assert settings.collections_filter_path == ["^/a$", "^/b$"]

    # Directly provided list[str] unaltered
    custom_paths = [
        r"^/collections(?:/(?P<collection_id>[^/]+))?$",
        r"^/collections/(?P<collection_id>[^/]+)/aggregate$",
    ]
    settings = Settings(
        **common_kwargs,
        collections_filter_path=custom_paths,
    )
    assert settings.collections_filter_path == custom_paths

    # Reject invalid regex at load
    with pytest.raises(ValueError, match="not a valid regular expression"):
        settings = Settings(
            **common_kwargs,
            items_filter_path=r"^/collections(?:/(?P<unclosed[^/]+))?$",
        )
