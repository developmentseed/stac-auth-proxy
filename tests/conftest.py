"""Pytest fixtures."""

import json
import os
import threading
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import uvicorn
from fastapi import FastAPI
from jwcrypto import jwk, jwt


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
    mock_oidc_config = {"jwks_uri": "https://example.com/jwks"}

    mock_jwks = {"keys": [public_key]}

    with (
        patch("urllib.request.urlopen") as mock_urlopen,
        patch("jwt.PyJWKClient.fetch_data") as mock_fetch_data,
    ):
        mock_oidc_config_response = MagicMock()
        mock_oidc_config_response.read.return_value = json.dumps(
            mock_oidc_config
        ).encode()
        mock_oidc_config_response.status = 200

        mock_urlopen.return_value.__enter__.return_value = mock_oidc_config_response
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
    """Create upstream API for testing purposes."""
    app = FastAPI(docs_url="/api.html", openapi_url="/api")

    for path, methods in {
        "/": [
            "GET",
        ],
        "/conformance": [
            "GET",
        ],
        "/queryables": [
            "GET",
        ],
        "/search": [
            "GET",
            "POST",
        ],
        "/collections": [
            "GET",
            "POST",
        ],
        "/collections/{collection_id}": [
            "GET",
            "PUT",
            "PATCH",
            "DELETE",
        ],
        "/collections/{collection_id}/items": [
            "GET",
            "POST",
        ],
        "/collections/{collection_id}/items/{item_id}": [
            "GET",
            "PUT",
            "PATCH",
            "DELETE",
        ],
        "/collections/{collection_id}/bulk_items": [
            "POST",
        ],
    }.items():
        for method in methods:
            # NOTE: declare routes per method separately to avoid warning of "Duplicate Operation ID ... for function <lambda>"
            app.add_api_route(
                path,
                lambda: {"id": f"Response from {method}@{path}"},
                methods=[method],
            )

    return app


@pytest.fixture(scope="session")
def source_api_server(source_api):
    """Run the source API in a background thread."""
    host, port = "127.0.0.1", 8000
    server = uvicorn.Server(
        uvicorn.Config(
            source_api,
            host=host,
            port=port,
        )
    )
    thread = threading.Thread(target=server.run)
    thread.start()
    yield f"http://{host}:{port}"
    server.should_exit = True
    thread.join()


@pytest.fixture(autouse=True, scope="module")
def mock_env():
    """Clear environment variables to avoid poluting configs from runtime env."""
    with patch.dict(os.environ, clear=True):
        yield
