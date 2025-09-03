"""Tests for the reverse proxy handler's header functionality."""

import pytest
from fastapi import Request

from stac_auth_proxy.handlers.reverse_proxy import ReverseProxyHandler


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"host", b"localhost:8000"),
            (b"user-agent", b"test-agent"),
            (b"accept", b"application/json"),
        ],
    }
    return Request(scope)


@pytest.fixture
def reverse_proxy_handler():
    """Create a reverse proxy handler instance."""
    return ReverseProxyHandler(upstream="http://upstream-api.com")


@pytest.mark.asyncio
async def test_basic_headers(mock_request, reverse_proxy_handler):
    """Test that basic headers are properly set."""
    headers = reverse_proxy_handler._prepare_headers(mock_request)

    # Check standard headers
    assert headers["Host"] == "upstream-api.com"
    assert headers["User-Agent"] == "test-agent"
    assert headers["Accept"] == "application/json"

    # Check modern forwarded header
    assert "Forwarded" in headers
    forwarded = headers["Forwarded"]
    assert "for=unknown" in forwarded
    assert "host=localhost:8000" in forwarded
    assert "proto=http" in forwarded
    assert "path=/" in forwarded

    # Check Via header
    assert headers["Via"] == "1.1 stac-auth-proxy"

    # Legacy headers should not be present by default
    assert "X-Forwarded-For" not in headers
    assert "X-Forwarded-Host" not in headers
    assert "X-Forwarded-Proto" not in headers
    assert "X-Forwarded-Path" not in headers


@pytest.mark.asyncio
async def test_legacy_forwarded_headers(mock_request):
    """Test that legacy X-Forwarded-* headers are set when enabled."""
    handler = ReverseProxyHandler(
        upstream="http://upstream-api.com", legacy_forwarded_headers=True
    )
    headers = handler._prepare_headers(mock_request)

    # Check legacy headers
    assert headers["X-Forwarded-For"] == "unknown"
    assert headers["X-Forwarded-Host"] == "localhost:8000"
    assert headers["X-Forwarded-Proto"] == "http"
    assert headers["X-Forwarded-Path"] == "/"

    # Modern Forwarded header should still be present
    assert "Forwarded" in headers


@pytest.mark.asyncio
async def test_override_host_disabled(mock_request):
    """Test that host override can be disabled."""
    handler = ReverseProxyHandler(
        upstream="http://upstream-api.com", override_host=False
    )
    headers = handler._prepare_headers(mock_request)
    assert headers["Host"] == "localhost:8000"


@pytest.mark.asyncio
async def test_custom_proxy_name(mock_request):
    """Test that custom proxy name is used in Via header."""
    handler = ReverseProxyHandler(
        upstream="http://upstream-api.com", proxy_name="custom-proxy"
    )
    headers = handler._prepare_headers(mock_request)
    assert headers["Via"] == "1.1 custom-proxy"


@pytest.mark.asyncio
async def test_forwarded_headers_with_client(mock_request):
    """Test forwarded headers when client information is available."""
    # Add client information to the request
    mock_request.scope["client"] = ("192.168.1.1", 12345)
    handler = ReverseProxyHandler(upstream="http://upstream-api.com")
    headers = handler._prepare_headers(mock_request)

    # Check modern Forwarded header
    forwarded = headers["Forwarded"]
    assert "for=192.168.1.1" in forwarded
    assert "host=localhost:8000" in forwarded
    assert "proto=http" in forwarded
    assert "path=/" in forwarded

    # Legacy headers should not be present by default
    assert "X-Forwarded-For" not in headers
    assert "X-Forwarded-Host" not in headers
    assert "X-Forwarded-Proto" not in headers
    assert "X-Forwarded-Path" not in headers


@pytest.mark.asyncio
async def test_legacy_forwarded_headers_with_client(mock_request):
    """Test legacy forwarded headers when client information is available."""
    mock_request.scope["client"] = ("192.168.1.1", 12345)
    handler = ReverseProxyHandler(
        upstream="http://upstream-api.com", legacy_forwarded_headers=True
    )
    headers = handler._prepare_headers(mock_request)

    # Check legacy headers
    assert headers["X-Forwarded-For"] == "192.168.1.1"
    assert headers["X-Forwarded-Host"] == "localhost:8000"
    assert headers["X-Forwarded-Proto"] == "http"
    assert headers["X-Forwarded-Path"] == "/"

    # Modern Forwarded header should still be present
    assert "Forwarded" in headers


@pytest.mark.asyncio
async def test_https_proto(mock_request):
    """Test that X-Forwarded-Proto is set correctly for HTTPS."""
    mock_request.scope["scheme"] = "https"
    handler = ReverseProxyHandler(upstream="http://upstream-api.com")
    headers = handler._prepare_headers(mock_request)

    # Check modern Forwarded header
    assert "proto=https" in headers["Forwarded"]

    # Legacy headers should not be present by default
    assert "X-Forwarded-Proto" not in headers


@pytest.mark.asyncio
async def test_https_proto_legacy(mock_request):
    """Test that X-Forwarded-Proto is set correctly for HTTPS with legacy headers."""
    mock_request.scope["scheme"] = "https"
    handler = ReverseProxyHandler(
        upstream="http://upstream-api.com", legacy_forwarded_headers=True
    )
    headers = handler._prepare_headers(mock_request)
    assert headers["X-Forwarded-Proto"] == "https"
    assert "proto=https" in headers["Forwarded"]


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


@pytest.mark.asyncio
async def test_nginx_proxy_headers_preserved():
    """Test that existing proxy headers from NGINX are preserved."""
    # Simulate a request that already has proxy headers set by NGINX
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"host", b"localhost:8000"),
            (b"user-agent", b"test-agent"),
            (b"x-forwarded-for", b"203.0.113.1, 198.51.100.1"),
            (b"x-forwarded-proto", b"https"),
            (b"x-forwarded-host", b"api.example.com"),
            (b"x-forwarded-path", b"/api/v1"),
        ],
    }
    request = Request(scope)
    handler = ReverseProxyHandler(upstream="http://upstream-api.com")
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


@pytest.mark.asyncio
async def test_nginx_proxy_headers_preserved_with_legacy():
    """Test that existing proxy headers from NGINX are preserved with legacy mode."""
    # Simulate a request that already has proxy headers set by NGINX
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"host", b"localhost:8000"),
            (b"user-agent", b"test-agent"),
            (b"x-forwarded-for", b"203.0.113.1, 198.51.100.1"),
            (b"x-forwarded-proto", b"https"),
            (b"x-forwarded-host", b"api.example.com"),
            (b"x-forwarded-path", b"/api/v1"),
        ],
    }
    request = Request(scope)
    handler = ReverseProxyHandler(
        upstream="http://upstream-api.com", legacy_forwarded_headers=True
    )
    headers = handler._prepare_headers(request)

    # Check that the existing proxy headers are preserved in both formats
    forwarded = headers["Forwarded"]
    assert "for=203.0.113.1, 198.51.100.1" in forwarded
    assert "host=api.example.com" in forwarded
    assert "proto=https" in forwarded
    assert "path=/api/v1" in forwarded

    # Legacy headers should also be preserved
    assert headers["X-Forwarded-For"] == "203.0.113.1, 198.51.100.1"
    assert headers["X-Forwarded-Host"] == "api.example.com"
    assert headers["X-Forwarded-Proto"] == "https"
    assert headers["X-Forwarded-Path"] == "/api/v1"


@pytest.mark.asyncio
async def test_partial_nginx_headers_fallback():
    """Test fallback behavior when only some proxy headers are present."""
    # Simulate a request with only some proxy headers set by NGINX
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"host", b"localhost:8000"),
            (b"user-agent", b"test-agent"),
            (b"x-forwarded-for", b"203.0.113.1"),
            (b"x-forwarded-proto", b"https"),
            # Missing X-Forwarded-Host and X-Forwarded-Path
        ],
    }
    request = Request(scope)
    handler = ReverseProxyHandler(upstream="http://upstream-api.com")
    headers = handler._prepare_headers(request)

    # Check that existing headers are preserved and missing ones fall back to request values
    forwarded = headers["Forwarded"]
    assert "for=203.0.113.1" in forwarded  # From existing header
    assert "host=localhost:8000" in forwarded  # Fallback to request host
    assert "proto=https" in forwarded  # From existing header
    assert "path=/" in forwarded  # Fallback to request path


@pytest.mark.asyncio
async def test_nginx_headers_with_client_info():
    """Test that NGINX headers take precedence over client info."""
    # Simulate a request with both client info and existing proxy headers
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "client": ("192.168.1.1", 12345),  # This should be ignored
        "headers": [
            (b"host", b"localhost:8000"),
            (b"user-agent", b"test-agent"),
            (b"x-forwarded-for", b"203.0.113.1, 198.51.100.1"),
        ],
    }
    request = Request(scope)
    handler = ReverseProxyHandler(upstream="http://upstream-api.com")
    headers = handler._prepare_headers(request)

    # The existing X-Forwarded-For should take precedence over client info
    forwarded = headers["Forwarded"]
    assert "for=203.0.113.1, 198.51.100.1" in forwarded
    assert "for=192.168.1.1" not in forwarded


@pytest.mark.asyncio
async def test_nginx_headers_with_https_scheme():
    """Test that NGINX headers take precedence over request scheme."""
    # Simulate an HTTPS request with existing proxy headers
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "scheme": "https",  # This should be ignored
        "headers": [
            (b"host", b"localhost:8000"),
            (b"user-agent", b"test-agent"),
            (b"x-forwarded-proto", b"http"),  # NGINX says it's HTTP
        ],
    }
    request = Request(scope)
    handler = ReverseProxyHandler(upstream="http://upstream-api.com")
    headers = handler._prepare_headers(request)

    # The existing X-Forwarded-Proto should take precedence over request scheme
    forwarded = headers["Forwarded"]
    assert "proto=http" in forwarded  # From existing header
    assert "proto=https" not in forwarded


@pytest.mark.asyncio
async def test_nginx_headers_with_custom_path():
    """Test that NGINX headers take precedence over request path."""
    # Simulate a request with a custom path and existing proxy headers
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/custom/path",
        "headers": [
            (b"host", b"localhost:8000"),
            (b"user-agent", b"test-agent"),
            (b"x-forwarded-path", b"/api/v1/root"),  # NGINX says different path
        ],
    }
    request = Request(scope)
    handler = ReverseProxyHandler(upstream="http://upstream-api.com")
    headers = handler._prepare_headers(request)

    # The existing X-Forwarded-Path should take precedence over request path
    forwarded = headers["Forwarded"]
    assert "path=/api/v1/root" in forwarded  # From existing header
    assert "path=/custom/path" not in forwarded


@pytest.mark.asyncio
async def test_nginx_headers_legacy_mode_preservation():
    """Test that NGINX headers are preserved in legacy mode without duplication."""
    # Simulate a request that already has proxy headers set by NGINX
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"host", b"localhost:8000"),
            (b"user-agent", b"test-agent"),
            (b"x-forwarded-for", b"203.0.113.1"),
            (b"x-forwarded-proto", b"https"),
            (b"x-forwarded-host", b"api.example.com"),
            (b"x-forwarded-path", b"/api/v1"),
        ],
    }
    request = Request(scope)
    handler = ReverseProxyHandler(
        upstream="http://upstream-api.com", legacy_forwarded_headers=True
    )
    headers = handler._prepare_headers(request)

    # Check that headers are preserved (not duplicated or overwritten)
    assert headers["X-Forwarded-For"] == "203.0.113.1"
    assert headers["X-Forwarded-Host"] == "api.example.com"
    assert headers["X-Forwarded-Proto"] == "https"
    assert headers["X-Forwarded-Path"] == "/api/v1"

    # Modern Forwarded header should also be present with the same values
    forwarded = headers["Forwarded"]
    assert "for=203.0.113.1" in forwarded
    assert "host=api.example.com" in forwarded
    assert "proto=https" in forwarded
    assert "path=/api/v1" in forwarded


@pytest.mark.asyncio
async def test_nginx_headers_case_insensitive():
    """Test that NGINX headers are handled case-insensitively."""
    # Simulate a request with mixed case proxy headers (some proxies do this)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"host", b"localhost:8000"),
            (b"user-agent", b"test-agent"),
            (b"X-Forwarded-For", b"203.0.113.1"),  # Mixed case
            (b"x-forwarded-proto", b"https"),  # Lower case
            (b"X-FORWARDED-HOST", b"api.example.com"),  # Upper case
        ],
    }
    request = Request(scope)
    handler = ReverseProxyHandler(upstream="http://upstream-api.com")
    headers = handler._prepare_headers(request)

    # All headers should be preserved regardless of case
    forwarded = headers["Forwarded"]
    assert "for=203.0.113.1" in forwarded
    assert "host=api.example.com" in forwarded
    assert "proto=https" in forwarded
