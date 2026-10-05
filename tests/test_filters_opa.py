"""Test OPA filter integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, Response

from stac_auth_proxy.filters.opa import Opa


@pytest.fixture
def opa_filter_factory():
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
async def test_opa_initialization(opa_filter_factory):
    """Test OPA initialization."""
    assert opa_filter_factory.host == "http://localhost:8181"
    assert opa_filter_factory.decision == "stac/filter"
    assert isinstance(opa_filter_factory.client, AsyncClient)


@pytest.mark.asyncio
async def test_opa_not_cached(opa_filter_factory, mock_opa_response):
    """Every request is sent to OPA, as policies may depend on method/path."""
    context = {"req": {"headers": {"authorization": "test-token"}}}

    with patch.object(
        opa_filter_factory.client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.return_value = mock_opa_response

        assert await opa_filter_factory(context) == "collection = 'test'"
        assert await opa_filter_factory(context) == "collection = 'test'"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_opa_error_handling(opa_filter_factory):
    """Test OPA error handling."""
    context = {"req": {"headers": {"authorization": "test-token"}}}

    with patch.object(
        opa_filter_factory.client, "post", new_callable=AsyncMock
    ) as mock_post:
        # Create a mock response that raises an exception on raise_for_status
        error_response = MagicMock(spec=Response)
        error_response.raise_for_status.side_effect = Exception("Internal server error")
        mock_post.return_value = error_response

        with pytest.raises(Exception):
            await opa_filter_factory(context)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers", [{"authorization": "Bearer t"}, {}], ids=["auth", "anon"]
)
async def test_opa_filter_depends_on_full_request(opa_filter_factory, headers):
    """A write must not reuse the filter OPA returned for a read with the same token."""

    async def post(url, json):
        req = json["input"]["req"]
        response = MagicMock(spec=Response)
        response.raise_for_status.return_value = response
        response.json.return_value = {"result": f"{req['method']} {req['path']}"}
        return response

    with patch.object(opa_filter_factory.client, "post", side_effect=post):
        ctx = {"req": {"method": "GET", "path": "/search", "headers": headers}}
        assert await opa_filter_factory(ctx) == "GET /search"
        ctx = {"req": {"method": "PUT", "path": "/collections/c", "headers": headers}}
        assert await opa_filter_factory(ctx) == "PUT /collections/c"
