"""Test authentication cases for the proxy app."""

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
