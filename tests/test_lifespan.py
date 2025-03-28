"""Tests for lifespan module."""

from dataclasses import dataclass
from unittest.mock import patch

import pytest
from starlette.middleware import Middleware
from starlette.types import ASGIApp

from stac_auth_proxy.utils.lifespan import check_conformance, check_server_health
from stac_auth_proxy.utils.middleware import required_conformance


@required_conformance("http://example.com/conformance")
@dataclass
class TestMiddleware:
    """Test middleware with required conformance."""

    app: ASGIApp


async def test_check_server_health_success(source_api_server):
    """Test successful health check."""
    await check_server_health(source_api_server)


async def test_check_server_health_failure():
    """Test health check failure."""
    with patch("asyncio.sleep") as mock_sleep:
        with pytest.raises(RuntimeError) as exc_info:
            await check_server_health("http://localhost:9999")
        assert "failed to respond after" in str(exc_info.value)
        # Verify sleep was called with exponential backoff
        assert mock_sleep.call_count > 0
        # First call should be with base delay
        # NOTE: When testing individually, the mock_sleep strangely has a first call of
        # 0 seconds (possibly by httpx), however when running all tests, this does not
        # occur. So, we have to check for 1.0 in the first two calls.
        assert 1.0 in [mock_sleep.call_args_list[i][0][0] for i in range(2)]
        # Last call should be with max delay
        assert mock_sleep.call_args_list[-1][0][0] == 5.0


async def test_check_conformance_success(source_api_server, source_api_responses):
    """Test successful conformance check."""
    middleware = [Middleware(TestMiddleware)]
    await check_conformance(middleware, source_api_server)


async def test_check_conformance_failure(source_api_server, source_api_responses):
    """Test conformance check failure."""
    # Override the conformance response to not include required conformance
    source_api_responses["/conformance"]["GET"] = {"conformsTo": []}

    middleware = [Middleware(TestMiddleware)]
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
        Middleware(TestMiddleware),
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
