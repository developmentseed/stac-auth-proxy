"""Tests for OpenAPI spec handling."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from utils import AppFactory

app_factory = AppFactory(
    oidc_discovery_url="https://samples.auth0.com/.well-known/openid-configuration"
)


def test_no_openapi_spec_endpoint(source_api_server):
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


def test_no_private_endpoints(source_api_server):
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
    assert "oidcAuth" not in openapi.get("components", {}).get("securitySchemes", {})


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


def test_oidc_in_openapi_spec_private_endpoints(
    source_api: FastAPI, source_api_server: str
):
    """When OpenAPI spec endpoint is set & endpoints are marked private, those endpoints are marked private in the spec."""
    private_endpoints = {
        # https://github.com/stac-api-extensions/collection-transaction/blob/v1.0.0-beta.1/README.md#methods
        "/collections": ["POST"],
        "/collections/{collection_id}": ["PUT", "PATCH", "DELETE"],
        # https://github.com/stac-api-extensions/transaction/blob/v1.0.0-rc.3/README.md#methods
        "/collections/{collection_id}/items": ["POST"],
        "/collections/{collection_id}/items/{item_id}": ["PUT", "PATCH", "DELETE"],
        # https://stac-utils.github.io/stac-fastapi/api/stac_fastapi/extensions/third_party/bulk_transactions/#bulktransactionextension
        "/collections/{collection_id}/bulk_items": ["POST"],
    }
    app = app_factory(
        upstream_url=source_api_server,
        openapi_spec_endpoint=source_api.openapi_url,
        private_endpoints=private_endpoints,
    )
    client = TestClient(app)
    openapi = client.get(source_api.openapi_url).raise_for_status().json()
    for path, methods in private_endpoints.items():
        for method in methods:
            openapi_path = openapi["paths"].get(path)
            assert openapi_path, f"Path {path} not found in OpenAPI spec"
            openapi_path_method = openapi_path.get(method.lower())
            assert (
                openapi_path_method
            ), f"Method {method.lower()!r} not found for path {path!r} in OpenAPI spec for path {path}"
            security = openapi_path_method.get("security")
            assert security, f"Security not found for {path!r} {method.lower()!r}"
            assert any(
                "oidcAuth" in s for s in security
            ), f'No "oidcAuth" in security for {path!r} {method.lower()!r}'
