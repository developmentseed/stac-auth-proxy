"""Tests for the reverse proxy handler's header functionality."""

import pytest
from fastapi import Request

from stac_auth_proxy.handlers.reverse_proxy import ReverseProxyHandler


def create_request(scope_overrides=None, headers=None):
    """Create a mock FastAPI request with custom scope and headers."""
    default_scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"host", b"localhost:8000"),
            (b"user-agent", b"test-agent"),
            (b"accept", b"application/json"),
        ],
    }

    if scope_overrides:
        default_scope.update(scope_overrides)

    if headers:
        default_scope["headers"] = headers

    return Request(default_scope)


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    return create_request()


@pytest.fixture
def reverse_proxy_handler():
    """Create a reverse proxy handler instance."""
    return ReverseProxyHandler(upstream="http://upstream-api.com")


@pytest.mark.parametrize(
    "legacy_headers,override_host,proxy_name,expected_host,expected_via",
    [
        (False, True, "stac-auth-proxy", "upstream-api.com", "1.1 stac-auth-proxy"),
        (True, True, "stac-auth-proxy", "upstream-api.com", "1.1 stac-auth-proxy"),
        (False, False, "stac-auth-proxy", "localhost:8000", "1.1 stac-auth-proxy"),
        (False, True, "custom-proxy", "upstream-api.com", "1.1 custom-proxy"),
    ],
)
@pytest.mark.asyncio
async def test_basic_headers(
    mock_request, legacy_headers, override_host, proxy_name, expected_host, expected_via
):
    """Test basic header functionality with various configurations."""
    handler = ReverseProxyHandler(
        upstream="http://upstream-api.com",
        legacy_forwarded_headers=legacy_headers,
        override_host=override_host,
        proxy_name=proxy_name,
    )
    headers = handler._prepare_headers(mock_request)

    # Check standard headers
    assert headers["Host"] == expected_host
    assert headers["User-Agent"] == "test-agent"
    assert headers["Accept"] == "application/json"
    assert headers["Via"] == expected_via

    # Check modern forwarded header
    assert "Forwarded" in headers
    forwarded = headers["Forwarded"]
    assert "for=unknown" in forwarded
    assert "host=localhost:8000" in forwarded
    assert "proto=http" in forwarded
    assert "path=/" in forwarded

    # Check legacy headers based on configuration
    if legacy_headers:
        assert headers["X-Forwarded-For"] == "unknown"
        assert headers["X-Forwarded-Host"] == "localhost:8000"
        assert headers["X-Forwarded-Proto"] == "http"
        assert headers["X-Forwarded-Path"] == "/"
    else:
        assert "X-Forwarded-For" not in headers
        assert "X-Forwarded-Host" not in headers
        assert "X-Forwarded-Proto" not in headers
        assert "X-Forwarded-Path" not in headers


@pytest.mark.parametrize("legacy_headers", [False, True])
@pytest.mark.asyncio
async def test_forwarded_headers_with_client(mock_request, legacy_headers):
    """Test forwarded headers when client information is available."""
    # Add client information to the request
    mock_request.scope["client"] = ("192.168.1.1", 12345)
    handler = ReverseProxyHandler(
        upstream="http://upstream-api.com", legacy_forwarded_headers=legacy_headers
    )
    headers = handler._prepare_headers(mock_request)

    # Check modern Forwarded header
    forwarded = headers["Forwarded"]
    assert "for=192.168.1.1" in forwarded
    assert "host=localhost:8000" in forwarded
    assert "proto=http" in forwarded
    assert "path=/" in forwarded

    # Check legacy headers based on configuration
    if legacy_headers:
        assert headers["X-Forwarded-For"] == "192.168.1.1"
        assert headers["X-Forwarded-Host"] == "localhost:8000"
        assert headers["X-Forwarded-Proto"] == "http"
        assert headers["X-Forwarded-Path"] == "/"
    else:
        assert "X-Forwarded-For" not in headers
        assert "X-Forwarded-Host" not in headers
        assert "X-Forwarded-Proto" not in headers
        assert "X-Forwarded-Path" not in headers


@pytest.mark.parametrize("legacy_headers", [False, True])
@pytest.mark.asyncio
async def test_https_proto(mock_request, legacy_headers):
    """Test that protocol is set correctly for HTTPS."""
    mock_request.scope["scheme"] = "https"
    handler = ReverseProxyHandler(
        upstream="http://upstream-api.com", legacy_forwarded_headers=legacy_headers
    )
    headers = handler._prepare_headers(mock_request)

    # Check modern Forwarded header
    assert "proto=https" in headers["Forwarded"]

    # Check legacy headers based on configuration
    if legacy_headers:
        assert headers["X-Forwarded-Proto"] == "https"
    else:
        assert "X-Forwarded-Proto" not in headers


@pytest.mark.asyncio
async def test_non_standard_port(mock_request):
    """Test handling of non-standard ports in host header."""
    mock_request.scope["headers"] = [
        (b"host", b"localhost:8080"),
        (b"user-agent", b"test-agent"),
    ]
    handler = ReverseProxyHandler(upstream="http://upstream-api.com:8080")
    headers = handler._prepare_headers(mock_request)
    assert headers["Host"] == "upstream-api.com:8080"


@pytest.mark.parametrize("legacy_headers", [False, True])
@pytest.mark.asyncio
async def test_nginx_proxy_headers_preserved(legacy_headers):
    """Test that existing proxy headers from NGINX are preserved."""
    # Simulate a request that already has proxy headers set by NGINX
    headers = [
        (b"host", b"localhost:8000"),
        (b"user-agent", b"test-agent"),
        (b"x-forwarded-for", b"203.0.113.1, 198.51.100.1"),
        (b"x-forwarded-proto", b"https"),
        (b"x-forwarded-host", b"api.example.com"),
        (b"x-forwarded-path", b"/api/v1"),
    ]
    request = create_request(headers=headers)
    handler = ReverseProxyHandler(
        upstream="http://upstream-api.com", legacy_forwarded_headers=legacy_headers
    )
    headers = handler._prepare_headers(request)

    # Check that the existing proxy headers are preserved in the Forwarded header
    forwarded = headers["Forwarded"]
    assert "for=203.0.113.1, 198.51.100.1" in forwarded
    assert "host=api.example.com" in forwarded
    assert "proto=https" in forwarded
    assert "path=/api/v1" in forwarded

    # The original headers should still be present (they're preserved from the request)
    assert headers["X-Forwarded-For"] == "203.0.113.1, 198.51.100.1"
    assert headers["X-Forwarded-Host"] == "api.example.com"
    assert headers["X-Forwarded-Proto"] == "https"
    assert headers["X-Forwarded-Path"] == "/api/v1"


@pytest.mark.parametrize(
    "scope_overrides,headers,expected_forwarded",
    [
        pytest.param(
            {},
            [
                (b"host", b"localhost:8000"),
                (b"user-agent", b"test-agent"),
                (b"x-forwarded-for", b"203.0.113.1"),
                (b"x-forwarded-proto", b"https"),
                # Missing X-Forwarded-Host and X-Forwarded-Path
            ],
            {
                "for": "203.0.113.1",  # From existing header
                "host": "localhost:8000",  # Fallback to request host
                "proto": "https",  # From existing header
                "path": "/",  # Fallback to request path
            },
            id="partial_headers_fallback",
        ),
        pytest.param(
            {"client": ("192.168.1.1", 12345)},  # This should be ignored
            [
                (b"host", b"localhost:8000"),
                (b"user-agent", b"test-agent"),
                (b"x-forwarded-for", b"203.0.113.1, 198.51.100.1"),
            ],
            {
                "for": "203.0.113.1, 198.51.100.1",  # From existing header
                "host": "localhost:8000",
                "proto": "http",
                "path": "/",
            },
            id="client_info_precedence",
        ),
        pytest.param(
            {"scheme": "https"},  # This should be ignored
            [
                (b"host", b"localhost:8000"),
                (b"user-agent", b"test-agent"),
                (b"x-forwarded-proto", b"http"),  # NGINX says it's HTTP
            ],
            {
                "for": "unknown",
                "host": "localhost:8000",
                "proto": "http",  # From existing header
                "path": "/",
            },
            id="scheme_precedence",
        ),
        pytest.param(
            {"path": "/custom/path"},
            [
                (b"host", b"localhost:8000"),
                (b"user-agent", b"test-agent"),
                (b"x-forwarded-path", b"/api/v1/root"),  # NGINX says different path
            ],
            {
                "for": "unknown",
                "host": "localhost:8000",
                "proto": "http",
                "path": "/api/v1/root",  # From existing header
            },
            id="path_precedence",
        ),
        pytest.param(
            {},
            [
                (b"host", b"localhost:8000"),
                (b"user-agent", b"test-agent"),
                (b"X-Forwarded-For", b"203.0.113.1"),  # Mixed case
                (b"x-forwarded-proto", b"https"),  # Lower case
                (b"X-FORWARDED-HOST", b"api.example.com"),  # Upper case
            ],
            {
                "for": "203.0.113.1",
                "host": "api.example.com",
                "proto": "https",
                "path": "/",
            },
            id="case_insensitive",
        ),
    ],
)
@pytest.mark.asyncio
async def test_nginx_headers_behavior(scope_overrides, headers, expected_forwarded):
    """Test various NGINX header behaviors and precedence rules."""
    request = create_request(scope_overrides=scope_overrides, headers=headers)
    handler = ReverseProxyHandler(upstream="http://upstream-api.com")
    result_headers = handler._prepare_headers(request)

    # Check that the Forwarded header contains expected values
    forwarded = result_headers["Forwarded"]
    for key, expected_value in expected_forwarded.items():
        assert f"{key}={expected_value}" in forwarded, (
            f"Expected {key}={expected_value} in {forwarded}"
        )


@pytest.mark.parametrize("legacy_headers", [False, True])
@pytest.mark.asyncio
async def test_x_forwarded_port_in_forwarded_header(legacy_headers):
    """Test that x-forwarded-port is included in the Forwarded header."""
    headers = [
        (b"host", b"localhost:8000"),
        (b"user-agent", b"test-agent"),
        (b"x-forwarded-port", b"443"),
        (b"x-forwarded-proto", b"https"),
        (b"x-forwarded-host", b"api.example.com"),
    ]
    request = create_request(headers=headers)
    handler = ReverseProxyHandler(
        upstream="http://upstream-api.com", legacy_forwarded_headers=legacy_headers
    )
    result_headers = handler._prepare_headers(request)

    # Check that the Forwarded header includes the port
    forwarded = result_headers["Forwarded"]
    assert "host=api.example.com:443" in forwarded, (
        f"Expected host=api.example.com:443 in {forwarded}"
    )
    assert "proto=https" in forwarded

    # Check that the x-forwarded-port header is preserved
    assert result_headers["X-Forwarded-Port"] == "443"
