"""Test OPA filter integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, Response

from stac_auth_proxy.filters.opa import Opa


@pytest.fixture
def opa_filter_generator():
    """Create an OPA instance for testing."""
    return Opa(host="http://localhost:8181", decision="stac/filter")


@pytest.fixture
def mock_opa_response():
    """Create a mock httpx Response."""
    response = MagicMock(spec=Response)
    response.json.return_value = {"result": "collection = 'test'"}
    response.raise_for_status.return_value = response
    return response


@pytest.mark.asyncio
async def test_opa_initialization(opa_filter_generator):
    """Test OPA initialization."""
    assert opa_filter_generator.host == "http://localhost:8181"
    assert opa_filter_generator.decision == "stac/filter"
    assert opa_filter_generator.cache_key == "req.headers.authorization"
    assert opa_filter_generator.cache_ttl == 5.0
    assert isinstance(opa_filter_generator.client, AsyncClient)
    assert opa_filter_generator.cache is not None


@pytest.mark.asyncio
async def test_opa_cache_hit(opa_filter_generator, mock_opa_response):
    """Test OPA cache hit behavior."""
    context = {"req": {"headers": {"authorization": "test-token"}}}

    # Mock the OPA response
    with patch.object(
        opa_filter_generator.client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.return_value = mock_opa_response

        # First call should hit OPA
        result = await opa_filter_generator(context)
        assert result == "collection = 'test'"
        assert mock_post.call_count == 1

        # Second call should use cache
        result = await opa_filter_generator(context)
        assert result == "collection = 'test'"
        assert mock_post.call_count == 1  # Still 1, no new call made


@pytest.mark.asyncio
async def test_opa_cache_miss(opa_filter_generator, mock_opa_response):
    """Test OPA cache miss behavior."""
    context = {"req": {"headers": {"authorization": "test-token"}}}

    with patch.object(
        opa_filter_generator.client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.return_value = mock_opa_response

        # First call with token1
        result = await opa_filter_generator(context)
        assert result == "collection = 'test'"
        assert mock_post.call_count == 1

        # Call with different token should miss cache
        context["req"]["headers"]["authorization"] = "different-token"
        result = await opa_filter_generator(context)
        assert result == "collection = 'test'"
        assert mock_post.call_count == 2  # New call made


@pytest.mark.asyncio
async def test_opa_error_handling(opa_filter_generator):
    """Test OPA error handling."""
    context = {"req": {"headers": {"authorization": "test-token"}}}

    with patch.object(
        opa_filter_generator.client, "post", new_callable=AsyncMock
    ) as mock_post:
        # Create a mock response that raises an exception on raise_for_status
        error_response = MagicMock(spec=Response)
        error_response.raise_for_status.side_effect = Exception("Internal server error")
        mock_post.return_value = error_response

        with pytest.raises(Exception):
            await opa_filter_generator(context)
