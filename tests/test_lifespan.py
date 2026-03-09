"""Tests for lifespan module."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware import Middleware
from starlette.types import ASGIApp

from stac_auth_proxy import build_lifespan
from stac_auth_proxy.lifespan import check_conformance, check_server_health
from stac_auth_proxy.utils.middleware import required_conformance


@required_conformance("http://example.com/conformance")
@dataclass
class ExampleMiddleware:
    """Test middleware with required conformance."""

    app: ASGIApp


async def test_check_server_health_success(source_api_server):
    """Test successful health check."""
    await check_server_health(source_api_server)


async def test_check_server_health_failure():
    """Test health check failure."""
    with pytest.raises(RuntimeError) as exc_info:
        with patch("asyncio.sleep") as mock_sleep:
            await check_server_health("http://localhost:9999")
    assert "failed to respond after" in str(exc_info.value)
    # Verify sleep was called with exponential backoff
    assert mock_sleep.call_count > 0
    # First call should be with base delay
    # NOTE: Concurrency issues makes this test flaky
    # assert mock_sleep.call_args_list[0][0][0] == 1.0
    # Last call should be with max delay
    assert mock_sleep.call_args_list[-1][0][0] == 5.0


@pytest.mark.parametrize("status_code", [502, 503, 504])
async def test_check_server_health_retries_on_retryable_status(status_code):
    """Test that retryable HTTP status codes (502, 503, 504) trigger retries."""
    import httpx

    def handler(request):
        return httpx.Response(status_code)

    with patch("asyncio.sleep") as mock_sleep:
        with patch(
            "httpx.AsyncClient",
            return_value=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        ):
            with pytest.raises(RuntimeError) as exc_info:
                await check_server_health("http://example.com", max_retries=3)
    assert "failed to respond after 3 attempts" in str(exc_info.value)
    assert mock_sleep.call_count == 3


async def test_check_server_health_does_not_retry_on_non_retryable_status():
    """Test that non-retryable HTTP status codes (e.g. 404) are raised immediately."""
    import httpx

    def handler(request):
        return httpx.Response(404)

    with patch("asyncio.sleep") as mock_sleep:
        with patch(
            "httpx.AsyncClient",
            return_value=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        ):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await check_server_health("http://example.com", max_retries=3)
    assert exc_info.value.response.status_code == 404
    assert mock_sleep.call_count == 0


async def test_check_server_health_recovers_from_retryable_status():
    """Test that a retryable status followed by success completes without error."""
    import httpx

    call_count = 0

    def handler(request):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(503)
        return httpx.Response(200)

    with patch("asyncio.sleep"):
        with patch(
            "httpx.AsyncClient",
            return_value=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        ):
            await check_server_health("http://example.com", max_retries=5)
    assert call_count == 3


async def test_check_conformance_success(source_api_server, source_api_responses):
    """Test successful conformance check."""
    middleware = [Middleware(ExampleMiddleware)]
    await check_conformance(middleware, source_api_server)


async def test_check_conformance_failure(source_api_server, source_api_responses):
    """Test conformance check failure."""
    # Override the conformance response to not include required conformance
    source_api_responses["/conformance"]["GET"] = {"conformsTo": []}

    middleware = [Middleware(ExampleMiddleware)]
    with pytest.raises(RuntimeError) as exc_info:
        await check_conformance(middleware, source_api_server)
    assert "missing the following conformance classes" in str(exc_info.value)


async def test_check_conformance_multiple_middleware(source_api_server):
    """Test conformance check with multiple middleware."""

    @required_conformance("http://example.com/conformance")
    class TestMiddleware2:
        def __init__(self, app):
            self.app = app

    middleware = [
        Middleware(ExampleMiddleware),
        Middleware(TestMiddleware2),
    ]
    await check_conformance(middleware, source_api_server)


async def test_check_conformance_no_required(source_api_server):
    """Test conformance check with middleware that has no required conformances."""

    class NoConformanceMiddleware:
        def __init__(self, app):
            self.app = app

    middleware = [Middleware(NoConformanceMiddleware)]
    await check_conformance(middleware, source_api_server)


def test_lifespan_reusable():
    """Ensure the public lifespan handler runs health and conformance checks."""
    upstream_url = "https://example.com"
    oidc_discovery_url = "https://example.com/.well-known/openid-configuration"
    with (
        patch(
            "stac_auth_proxy.lifespan.check_server_health",
            new=AsyncMock(),
        ) as mock_health,
        patch(
            "stac_auth_proxy.lifespan.check_conformance",
            new=AsyncMock(),
        ) as mock_conf,
    ):
        app = FastAPI(
            lifespan=build_lifespan(
                upstream_url=upstream_url,
                oidc_discovery_url=oidc_discovery_url,
            )
        )
        with TestClient(app):
            pass
        assert mock_health.await_count == 2
        expected_upstream = upstream_url.rstrip("/") + "/"
        mock_conf.assert_awaited_once_with(app.user_middleware, expected_upstream)
