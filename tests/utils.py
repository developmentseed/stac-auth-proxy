"""Utilities for testing."""

from dataclasses import dataclass
from typing import Callable
import json
from urllib.parse import parse_qs, unquote

import httpx

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
    parsed = parse_qs(qs)

    result = {}
    for key, value_list in parsed.items():
        value = value_list[0]
        if key == "filter" and parsed.get("filter-lang") == "cql2-json":
            decoded_str = unquote(value)
            result[key] = json.loads(decoded_str)
        else:
            result[key] = unquote(value)

    return result
