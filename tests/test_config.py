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


@pytest.mark.parametrize(
    "root_path, expected",
    [("", ""), ("/", ""), ("/stac", "/stac"), ("/stac/", "/stac")],
)
def test_root_path_normalized(root_path, expected):
    """Trailing slashes are dropped from root_path."""
    settings = Settings(
        upstream_url="https://example.com",
        oidc_discovery_url="https://example.com/.well-known/openid-configuration",
        root_path=root_path,
    )
    assert settings.root_path == expected


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


def test_cors_env_vars(monkeypatch):
    """The documented CORS_* env vars are honored alongside other nested settings."""
    monkeypatch.setenv("UPSTREAM_URL", "http://upstream")
    monkeypatch.setenv("OIDC_DISCOVERY_URL", "http://oidc/.well-known/x")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://a.com,https://b.com")
    monkeypatch.setenv("CORS_ALLOW_CREDENTIALS", "false")
    monkeypatch.setenv("CORS_MAX_AGE", "10")
    monkeypatch.setenv("ITEMS_FILTER_CLS", "stac_auth_proxy.filters:Template")
    monkeypatch.setenv("ITEMS_FILTER_ARGS", '["true"]')
    settings = Settings()
    assert list(settings.cors.allow_origins) == ["https://a.com", "https://b.com"]
    assert settings.cors.allow_credentials is False
    assert settings.cors.max_age == 10
    assert settings.items_filter.cls == "stac_auth_proxy.filters:Template"
    assert list(settings.items_filter.args) == ["true"]


def test_cors_json_env_var(monkeypatch):
    """The CORS={...} JSON env var form is honored."""
    monkeypatch.setenv("UPSTREAM_URL", "http://upstream")
    monkeypatch.setenv("OIDC_DISCOVERY_URL", "http://oidc/.well-known/x")
    monkeypatch.setenv("CORS", '{"allow_origins": ["https://a.com"]}')
    assert list(Settings().cors.allow_origins) == ["https://a.com"]


def test_cors_env_var_json_list(monkeypatch):
    """A CORS_* list env var also accepts the JSON-list form."""
    monkeypatch.setenv("UPSTREAM_URL", "http://upstream")
    monkeypatch.setenv("OIDC_DISCOVERY_URL", "http://oidc/.well-known/x")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", '["https://a.com", "https://b.com"]')
    assert list(Settings().cors.allow_origins) == ["https://a.com", "https://b.com"]
