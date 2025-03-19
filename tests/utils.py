"""Utilities for testing."""

import json
from dataclasses import dataclass
from typing import Callable, cast
from unittest.mock import MagicMock
from urllib.parse import parse_qs, unquote

import httpx
from httpx import Headers, Request

from stac_auth_proxy import Settings, create_app


class AppFactory:
    """Factory for creating test apps with default settings."""

    def __init__(self, **defaults):
        """Initialize the factory with default settings."""
        self.defaults = defaults

    def __call__(self, *, upstream_url, **overrides) -> Callable:
        """Create a new app with the given overrides."""
        return create_app(
            Settings.model_validate(
                {
                    **self.defaults,
                    **overrides,
                    "upstream_url": upstream_url,
                },
            )
        )


@dataclass
class SingleChunkAsyncStream(httpx.AsyncByteStream):
    """Mock async stream that returns a single chunk of data."""

    body: bytes

    async def __aiter__(self):
        """Return a single chunk of data."""
        yield self.body


def single_chunk_async_stream_response(
    body: bytes, status_code=200, headers={"content-type": "application/json"}
):
    """Create a response with a single chunk of data."""
    return httpx.Response(
        stream=SingleChunkAsyncStream(body),
        status_code=status_code,
        headers=headers,
    )


def parse_query_string(qs: str) -> dict:
    """Parse a query string into a dictionary."""
    # Python's parse_qs will turn dicts into strings (e.g. parse_qs('foo={"x":"y"}') == {'foo': ['{"x":"y"}']})
    # so we need some special tooling to examine the query params and compare them to expected values
    parsed = parse_qs(qs)

    result = {}
    for key, value_list in parsed.items():
        value = value_list[0]
        if key == "filter" and parsed.get("filter-lang") == ["cql2-json"]:
            decoded_str = unquote(value)
            result[key] = json.loads(decoded_str)
        else:
            result[key] = unquote(value)

    return result


async def get_upstream_request(mock_upstream: MagicMock) -> "UpstreamRequest":
    """Fetch the raw body and query params from the single upstream request."""
    assert mock_upstream.call_count == 1
    [request] = cast(list[Request], mock_upstream.call_args[0])
    req_body = request._streamed_body
    return UpstreamRequest(
        body=req_body.decode(),
        query_params=parse_query_string(request.url.query.decode("utf-8")),
        headers=request.headers,
    )


@dataclass
class UpstreamRequest:
    """The raw body and query params from the single upstream request."""

    body: str
    query_params: dict
    headers: Headers
