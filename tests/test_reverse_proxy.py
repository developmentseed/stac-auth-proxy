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
