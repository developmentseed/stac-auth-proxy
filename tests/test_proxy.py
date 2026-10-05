"""Test authentication cases for the proxy app."""

from urllib.parse import parse_qsl

import pytest
from fastapi.testclient import TestClient
from utils import AppFactory, get_upstream_request

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
    default_public=True,
    public_endpoints={},
    private_endpoints={},
)


async def test_proxied_headers_no_encoding(source_api_server, mock_upstream):
    """Clients that don't accept encoding should not receive it."""
    test_app = app_factory(upstream_url=source_api_server)

    client = TestClient(test_app)
    req = client.build_request(method="GET", url="/", headers={})
    for h in req.headers:
        if h in ["accept-encoding"]:
            del req.headers[h]
    client.send(req)

    proxied_request = await get_upstream_request(mock_upstream)
    assert "accept-encoding" not in proxied_request.headers


async def test_proxied_headers_with_encoding(source_api_server, mock_upstream):
    """Clients that do accept encoding should receive it."""
    test_app = app_factory(upstream_url=source_api_server)

    client = TestClient(test_app)
    req = client.build_request(
        method="GET", url="/", headers={"accept-encoding": "gzip"}
    )
    client.send(req)

    proxied_request = await get_upstream_request(mock_upstream)
    assert proxied_request.headers.get("accept-encoding") == "gzip"


@pytest.mark.parametrize(
    "raw_query, expected",
    [
        (b"x=#&c=1", {"x": "#", "c": "1"}),
        ("c=café".encode(), {"c": "café"}),
        (b"a=%26b&c=1+2", {"a": "&b", "c": "1 2"}),
    ],
)
async def test_raw_query_string_forwarded(
    source_api_server, mock_upstream, raw_query, expected
):
    """The full query string is forwarded, not request.url.query (truncated at '#')."""
    app = app_factory(upstream_url=source_api_server)

    async def with_raw_query(scope, receive, send):
        # TestClient can't send a raw "#" (it's taken as a fragment), a server can
        if scope["type"] == "http":
            scope = {**scope, "query_string": raw_query}
        await app(scope, receive, send)

    TestClient(with_raw_query).post("/search", json={})
    [request] = mock_upstream.call_args[0]
    assert dict(parse_qsl(request.url.query.decode())) == expected
