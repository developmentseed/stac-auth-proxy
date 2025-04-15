"""Pytest fixtures."""

import os
import socket
import threading
from functools import partial
from typing import Any, AsyncGenerator
from unittest.mock import DEFAULT, AsyncMock, MagicMock, patch

import pytest
import uvicorn
from fastapi import FastAPI
from jwcrypto import jwk, jwt
from starlette_cramjam.middleware import CompressionMiddleware
from utils import single_chunk_async_stream_response


@pytest.fixture
def test_key() -> jwk.JWK:
    """Generate a test RSA key."""
    return jwk.JWK.generate(
        kty="RSA", size=2048, kid="test", use="sig", e="AQAB", alg="RS256"
    )


@pytest.fixture
def public_key(test_key: jwk.JWK) -> dict[str, Any]:
    """Export public key."""
    return test_key.export_public(as_dict=True)


@pytest.fixture(autouse=True)
def mock_jwks(public_key: dict[str, Any]):
    """Mock JWKS endpoint."""
    mock_oidc_config = {
        "jwks_uri": "https://example.com/jwks",
        "authorization_endpoint": "https://example.com/auth",
        "token_endpoint": "https://example.com/token",
        "scopes_supported": ["openid", "profile", "email", "collection:create"],
    }

    mock_jwks = {"keys": [public_key]}

    with (
        patch("httpx.get") as mock_urlopen,
        patch("jwt.PyJWKClient.fetch_data") as mock_fetch_data,
    ):
        mock_oidc_config_response = MagicMock()
        mock_oidc_config_response.json.return_value = mock_oidc_config
        mock_oidc_config_response.status = 200

        mock_urlopen.return_value = mock_oidc_config_response
        mock_fetch_data.return_value = mock_jwks
        yield mock_urlopen


@pytest.fixture
def token_builder(test_key: jwk.JWK):
    """Generate a valid JWT token builder."""

    def build_token(payload: dict[str, Any], key=None) -> str:
        jwt_token = jwt.JWT(
            header={k: test_key.get(k) for k in ["alg", "kid"]},
            claims=payload,
        )
        jwt_token.make_signed_token(key or test_key)
        return jwt_token.serialize()

    return build_token


@pytest.fixture(scope="session")
def source_api():
    """
    Create upstream API for testing purposes.

    You can customize the response for each endpoint by passing a dict of responses:
    {
        "path": {
            "method": response_body
        }
    }
    """
    app = FastAPI(docs_url="/api.html", openapi_url="/api")

    app.add_middleware(CompressionMiddleware, minimum_size=0, compression_level=1)

    # Default responses for each endpoint
    default_responses = {
        "/": {"GET": {"id": "Response from GET@"}},
        "/conformance": {"GET": {"conformsTo": ["http://example.com/conformance"]}},
        "/queryables": {"GET": {"queryables": {}}},
        "/search": {
            "GET": {"type": "FeatureCollection", "features": []},
            "POST": {"type": "FeatureCollection", "features": []},
        },
        "/collections": {
            "GET": {"collections": []},
            "POST": {"id": "Response from POST@"},
        },
        "/collections/{collection_id}": {
            "GET": {"id": "Response from GET@"},
            "PUT": {"id": "Response from PUT@"},
            "PATCH": {"id": "Response from PATCH@"},
            "DELETE": {"id": "Response from DELETE@"},
        },
        "/collections/{collection_id}/items": {
            "GET": {"type": "FeatureCollection", "features": []},
            "POST": {"id": "Response from POST@"},
        },
        "/collections/{collection_id}/items/{item_id}": {
            "GET": {"id": "Response from GET@"},
            "PUT": {"id": "Response from PUT@"},
            "PATCH": {"id": "Response from PATCH@"},
            "DELETE": {"id": "Response from DELETE@"},
        },
        "/collections/{collection_id}/bulk_items": {
            "POST": {"id": "Response from POST@"},
        },
    }

    # Store responses in app state
    app.state.default_responses = default_responses

    def get_response(path: str, method: str) -> dict:
        """Get response for a given path and method."""
        return app.state.default_responses.get(path, {}).get(
            method, {"id": f"Response from {method}@{path}"}
        )

    for path, methods in default_responses.items():
        for method in methods:
            app.add_api_route(
                path,
                partial(get_response, path, method),
                methods=[method],
            )

    return app


@pytest.fixture
def source_api_responses(source_api):
    """
    Fixture to override source API responses for specific tests.

    Usage:
        def test_something(source_api_responses):
            # Override responses for specific endpoints
            source_api_responses["/collections"]["GET"] = {"collections": [{"id": "test"}]}
            source_api_responses["/search"]["POST"] = {"type": "FeatureCollection", "features": [{"id": "test"}]}

            # Your test code here
    """
    # Get the default responses from the source_api fixture
    default_responses = source_api.state.default_responses

    # Create a new dict that can be modified by tests
    responses = {}
    for path, methods in default_responses.items():
        responses[path] = methods.copy()

    # Store the responses in the app state for the get_response function to use
    source_api.state.default_responses = responses

    yield responses

    # Restore the original responses after the test
    source_api.state.default_responses = default_responses


@pytest.fixture(scope="session")
def free_port():
    """Get a free port."""
    sock = socket.socket()
    # Needed for Github Actions, https://stackoverflow.com/a/4466035
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", 0))
    return sock.getsockname()[1]


@pytest.fixture(scope="session")
def source_api_server(source_api, free_port):
    """Run the source API in a background thread."""
    host = "127.0.0.1"
    server = uvicorn.Server(
        uvicorn.Config(
            source_api,
            host=host,
            port=free_port,
        )
    )
    thread = threading.Thread(target=server.run)
    thread.start()
    yield f"http://{host}:{free_port}"
    server.should_exit = True
    thread.join()


@pytest.fixture(autouse=True, scope="session")
def mock_env():
    """Clear environment variables to avoid poluting configs from runtime env."""
    with patch.dict(os.environ, clear=True):
        yield


@pytest.fixture
async def mock_upstream() -> AsyncGenerator[MagicMock, None]:
    """Mock the HTTPX send method. Useful when we want to inspect the request is sent to upstream API."""
    # NOTE: This fixture will interfere with the source_api_responses fixture

    async def store_body(request, **kwargs):
        """Exhaust and store the request body."""
        _streamed_body = b""
        async for chunk in request.stream:
            _streamed_body += chunk
        setattr(request, "_streamed_body", _streamed_body)
        return DEFAULT

    with patch(
        "stac_auth_proxy.handlers.reverse_proxy.httpx.AsyncClient.send",
        new_callable=AsyncMock,
        side_effect=store_body,
        return_value=single_chunk_async_stream_response(b"{}"),
    ) as mock_send_method:
        yield mock_send_method
