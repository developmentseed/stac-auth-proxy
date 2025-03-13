"""Tests for OpenAPI spec handling."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from utils import AppFactory

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration"
)


def test_no_openapi_spec_endpoint(source_api_server: str):
    """When no OpenAPI spec endpoint is set, the proxied OpenAPI spec is unaltered."""
    app = app_factory(
        upstream_url=source_api_server,
        openapi_spec_endpoint=None,
    )
    client = TestClient(app)
    response = client.get("/api")
    assert response.status_code == 200
    openapi = response.json()
    assert "info" in openapi
    assert "openapi" in openapi
    assert "paths" in openapi
    assert "oidcAuth" not in openapi.get("components", {}).get("securitySchemes", {})


def test_no_private_endpoints(source_api_server: str):
    """When no endpoints are private, the proxied OpenAPI spec is unaltered."""
    app = app_factory(
        upstream_url=source_api_server,
        openapi_spec_endpoint="/api",
        private_endpoints={},
        default_public=True,
    )
    client = TestClient(app)
    response = client.get("/api")
    assert response.status_code == 200
    openapi = response.json()
    assert "info" in openapi
    assert "openapi" in openapi
    assert "paths" in openapi


def test_oidc_in_openapi_spec(source_api: FastAPI, source_api_server: str):
    """When OpenAPI spec endpoint is set, the proxied OpenAPI spec is augmented with oidc details."""
    app = app_factory(
        upstream_url=source_api_server,
        openapi_spec_endpoint=source_api.openapi_url,
    )
    client = TestClient(app)
    response = client.get(source_api.openapi_url)
    assert response.status_code == 200
    openapi = response.json()
    assert "info" in openapi
    assert "openapi" in openapi
    assert "paths" in openapi
    assert "oidcAuth" in openapi.get("components", {}).get("securitySchemes", {})


@pytest.mark.parametrize("compression_type", ["gzip", "br", "deflate"])
def test_oidc_in_openapi_spec_compressed(
    source_api: FastAPI, source_api_server: str, compression_type: str
):
    """When OpenAPI spec endpoint is set, the proxied OpenAPI spec is augmented with oidc details."""
    app = app_factory(
        upstream_url=source_api_server,
        openapi_spec_endpoint=source_api.openapi_url,
    )
    client = TestClient(app)

    # Test with gzip acceptance
    response = client.get(
        source_api.openapi_url, headers={"Accept-Encoding": compression_type}
    )
    assert response.status_code == 200
    assert response.headers.get("content-encoding") == compression_type
    assert response.headers.get("content-type") == "application/json"

    # TestClient automatically decompresses
    openapi = response.json()
    assert "info" in openapi
    assert "openapi" in openapi
    assert "paths" in openapi
    assert "oidcAuth" in openapi.get("components", {}).get("securitySchemes", {})

    # # Test without gzip acceptance
    # response = client.get(source_api.openapi_url)
    # assert response.status_code == 200
    # assert "content-encoding" not in response.headers
    # assert response.headers.get("content-type") == "application/json"

    # # Should get same content
    # openapi = response.json()
    # assert "info" in openapi
    # assert "openapi" in openapi
    # assert "paths" in openapi
    # assert "oidcAuth" in openapi.get("components", {}).get("securitySchemes", {})


def test_oidc_in_openapi_spec_private_endpoints(
    source_api: FastAPI, source_api_server: str
):
    """When OpenAPI spec endpoint is set & endpoints are marked private, those endpoints are marked private in the spec."""
    private_endpoints = {
        # https://github.com/stac-api-extensions/collection-transaction/blob/v1.0.0-beta.1/README.md#methods
        r"^/collections$": ["POST"],
        r"^/collections/([^/]+)$": ["PUT", "PATCH", "DELETE"],
        # https://github.com/stac-api-extensions/transaction/blob/v1.0.0-rc.3/README.md#methods
        r"^/collections/([^/]+)/items$": ["POST"],
        r"^/collections/([^/]+)/items/([^/]+)$": ["PUT", "PATCH", "DELETE"],
        # https://stac-utils.github.io/stac-fastapi/api/stac_fastapi/extensions/third_party/bulk_transactions/#bulktransactionextension
        r"^/collections/([^/]+)/bulk_items$": ["POST"],
    }
    app = app_factory(
        upstream_url=source_api_server,
        openapi_spec_endpoint=source_api.openapi_url,
        default_public=True,
        private_endpoints=private_endpoints,
    )
    client = TestClient(app)

    openapi = client.get(source_api.openapi_url).raise_for_status().json()

    expected_auth = {
        "/collections": ["POST"],
        "/collections/{collection_id}": ["PUT", "PATCH", "DELETE"],
        "/collections/{collection_id}/items": ["POST"],
        "/collections/{collection_id}/items/{item_id}": ["PUT", "PATCH", "DELETE"],
        "/collections/{collection_id}/bulk_items": ["POST"],
    }
    for path, method_config in openapi["paths"].items():
        for method, config in method_config.items():
            security = config.get("security")
            path_in_expected_auth = path in expected_auth
            method_in_expected_auth = any(
                method.casefold() == m.casefold() for m in expected_auth.get(path, [])
            )
            if security:
                assert path_in_expected_auth
                assert method_in_expected_auth
            else:
                assert not all([path_in_expected_auth, method_in_expected_auth])


def test_oidc_in_openapi_spec_public_endpoints(
    source_api: FastAPI, source_api_server: str
):
    """When OpenAPI spec endpoint is set & endpoints are marked public, those endpoints are not marked private in the spec."""
    public = {r"^/queryables$": ["GET"], r"^/api": ["GET"]}
    app = app_factory(
        upstream_url=source_api_server,
        openapi_spec_endpoint=source_api.openapi_url,
        default_public=False,
        public_endpoints=public,
    )
    client = TestClient(app)

    openapi = client.get(source_api.openapi_url).raise_for_status().json()

    expected_auth = {"/queryables": ["GET"]}
    for path, method_config in openapi["paths"].items():
        for method, config in method_config.items():
            security = config.get("security")
            if security:
                assert path not in expected_auth
            else:
                assert path in expected_auth
                assert any(
                    method.casefold() == m.casefold() for m in expected_auth[path]
                )
