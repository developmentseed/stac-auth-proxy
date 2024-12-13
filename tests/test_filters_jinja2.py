"""Tests for Jinja2 CQL2 filter."""

from dataclasses import dataclass
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient
from utils import AppFactory

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
    default_public=False,
)


@pytest.fixture
def mock_send() -> Generator[MagicMock, None, None]:
    """Mock the HTTPX send method. Useful when we want to inspect the request is sent to upstream API."""
    with patch(
        "stac_auth_proxy.handlers.reverse_proxy.httpx.AsyncClient.send",
        new_callable=AsyncMock,
    ) as mock_send_method:
        yield mock_send_method


@dataclass
class SingleChunkAsyncStream(httpx.AsyncByteStream):
    """Mock async stream that returns a single chunk of data."""

    body: bytes

    async def __aiter__(self):
        """Return a single chunk of data."""
        yield self.body


def test_collections_filter_contained_by_token(
    mock_send, source_api_server, token_builder
):
    """Test that the collections filter is applied correctly."""
    # Mock response from upstream API
    mock_send.return_value = httpx.Response(
        200,
        stream=SingleChunkAsyncStream(b"{}"),
        headers={"content-type": "application/json"},
    )

    app = app_factory(
        upstream_url=source_api_server,
        collections_filter={
            "cls": "stac_auth_proxy.filters.Template",
            "args": [
                "A_CONTAINEDBY(id, ('{{ token.collections | join(\"', '\") }}' ))"
            ],
        },
    )

    auth_token = token_builder({"collections": ["foo", "bar"]})
    client = TestClient(
        app,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    response = client.get("/collections")
    assert response.status_code == 200
    assert mock_send.call_count == 1
    [r] = mock_send.call_args[0]
    assert parse_qs(r.url.query.decode()) == {
        "filter": ["a_containedby(id, ('foo', 'bar'))"]
    }
