"""Test CORS handling and proxy_options setting."""

import pytest
from fastapi.testclient import TestClient
from utils import AppFactory

from stac_auth_proxy.config import CorsSettings

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
    default_public=False,
    public_endpoints={},
    private_endpoints={},
)


class TestCorsSettingsParsing:
    """Test CorsSettings field validation and env var parsing."""

    def test_defaults(self):
        """Default CorsSettings values match expected auth-proxy defaults."""
        settings = CorsSettings()
        assert list(settings.allow_origins) == ["*"]
        assert list(settings.allow_methods) == ["*"]
        assert list(settings.allow_headers) == ["*"]
        assert settings.allow_credentials is True
        assert list(settings.expose_headers) == []
        assert settings.max_age == 600

    @pytest.mark.parametrize(
        "input_val,expected",
        [
            (
                "http://localhost:3000,https://example.com",
                ["http://localhost:3000", "https://example.com"],
            ),
            (
                "http://localhost:3000 , https://example.com ",
                ["http://localhost:3000", "https://example.com"],
            ),
            ("*", ["*"]),
            (["http://a.com", "http://b.com"], ["http://a.com", "http://b.com"]),
        ],
    )
    def test_parse_list_origins(self, input_val, expected):
        """Comma-separated strings and lists are parsed into origin lists."""
        settings = CorsSettings(allow_origins=input_val)
        assert list(settings.allow_origins) == expected

    @pytest.mark.parametrize(
        "input_val,expected",
        [
            ("GET,POST", ["GET", "POST"]),
            ("Content-Type,Authorization", ["Content-Type", "Authorization"]),
        ],
    )
    def test_parse_list_methods_and_headers(self, input_val, expected):
        """Comma-separated strings are parsed for methods and headers fields."""
        settings = CorsSettings(allow_methods=input_val)
        assert list(settings.allow_methods) == expected
        settings = CorsSettings(allow_headers=input_val)
        assert list(settings.allow_headers) == expected


class TestCorsDefaultBehavior:
    """Test proxy_options=False (default): CORS handled locally."""

    def test_preflight_returns_cors_headers(self, source_api_server):
        """Preflight request gets 200 with CORS headers from the proxy."""
        test_app = app_factory(upstream_url=source_api_server)
        client = TestClient(test_app)

        response = client.options(
            "/collections",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://example.com"
        assert response.headers["access-control-allow-credentials"] == "true"

    def test_origin_reflected_not_wildcard(self, source_api_server):
        """With default credentials=True, origin is reflected rather than literal *."""
        test_app = app_factory(upstream_url=source_api_server)
        client = TestClient(test_app)

        response = client.options(
            "/collections",
            headers={
                "Origin": "https://my-app.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert (
            response.headers["access-control-allow-origin"]
            == "https://my-app.example.com"
        )
        assert response.headers["access-control-allow-origin"] != "*"

    def test_cors_headers_on_401(self, source_api_server):
        """401 responses include CORS headers so browsers can read the error."""
        test_app = app_factory(upstream_url=source_api_server)
        client = TestClient(test_app)

        response = client.get(
            "/collections",
            headers={"Origin": "https://example.com"},
        )

        assert response.status_code == 401
        assert response.headers["access-control-allow-origin"] == "https://example.com"
        assert response.headers["access-control-allow-credentials"] == "true"

    def test_no_cors_headers_without_origin(self, source_api_server):
        """Requests without Origin header get no CORS headers."""
        test_app = app_factory(upstream_url=source_api_server)
        client = TestClient(test_app)

        response = client.get("/collections")

        assert response.status_code == 401
        assert "access-control-allow-origin" not in response.headers

    def test_preflight_not_proxied_to_upstream(self, source_api_server):
        """Preflight requests are handled by CORSMiddleware, not proxied to upstream."""
        test_app = app_factory(upstream_url=source_api_server)
        client = TestClient(test_app)

        response = client.options(
            "/collections",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        # CORSMiddleware responds with plain text "OK", not upstream's JSON body
        assert response.text == "OK"

    def test_custom_origins(self, source_api_server):
        """Only configured origins get CORS headers."""
        test_app = app_factory(
            upstream_url=source_api_server,
            cors={"allow_origins": ["https://allowed.com"]},
        )
        client = TestClient(test_app)

        # Allowed origin
        response = client.options(
            "/collections",
            headers={
                "Origin": "https://allowed.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://allowed.com"

        # Disallowed origin
        response = client.options(
            "/collections",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 400

    def test_credentials_disabled_sends_wildcard(self, source_api_server):
        """When allow_credentials=False, literal * is sent."""
        test_app = app_factory(
            upstream_url=source_api_server,
            cors={"allow_credentials": False},
        )
        client = TestClient(test_app)

        response = client.options(
            "/collections",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "*"
        assert "access-control-allow-credentials" not in response.headers


class TestProxyOptionsEnabled:
    """Test proxy_options=True: OPTIONS forwarded to upstream."""

    def test_options_proxied_to_upstream(self, source_api_server):
        """OPTIONS requests are forwarded to upstream and return upstream's response."""
        test_app = app_factory(
            upstream_url=source_api_server,
            proxy_options=True,
        )
        client = TestClient(test_app)

        response = client.options("/collections")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "Response from OPTIONS@"

    def test_no_cors_middleware_headers(self, source_api_server):
        """With proxy_options=True, the proxy does not add CORS headers."""
        test_app = app_factory(
            upstream_url=source_api_server,
            proxy_options=True,
        )
        client = TestClient(test_app)

        response = client.get(
            "/collections",
            headers={"Origin": "https://example.com"},
        )

        # Upstream doesn't set CORS headers in the test fixture
        assert "access-control-allow-origin" not in response.headers
