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
    assert response.json()


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


def test_auth_scheme_name_override(source_api: FastAPI, source_api_server: str):
    """When auth_scheme_name is overridden, the OpenAPI spec uses the custom name."""
    custom_name = "customAuth"
    app = app_factory(
        upstream_url=source_api_server,
        openapi_spec_endpoint=source_api.openapi_url,
        openapi_auth_scheme_name=custom_name,
    )
    client = TestClient(app)
    response = client.get(source_api.openapi_url)
    assert response.status_code == 200
    openapi = response.json()
    security_schemes = openapi.get("components", {}).get("securitySchemes", {})
    assert custom_name in security_schemes
    assert "oidcAuth" not in security_schemes


def test_auth_scheme_override(source_api: FastAPI, source_api_server: str):
    """When auth_scheme_override is provided, the OpenAPI spec uses the custom scheme."""
    custom_scheme = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Custom JWT authentication",
    }
    app = app_factory(
        upstream_url=source_api_server,
        openapi_spec_endpoint=source_api.openapi_url,
        openapi_auth_scheme_override=custom_scheme,
    )
    client = TestClient(app)
    response = client.get(source_api.openapi_url)
    assert response.status_code == 200
    openapi = response.json()
    security_schemes = openapi.get("components", {}).get("securitySchemes", {})
    assert "oidcAuth" in security_schemes
    assert security_schemes["oidcAuth"] == custom_scheme


def test_root_path_in_openapi_spec(source_api: FastAPI, source_api_server: str):
    """When root_path is set, the OpenAPI spec includes the root path in the servers field."""
    root_path = "/api/v1"
    app = app_factory(
        upstream_url=source_api_server,
        openapi_spec_endpoint=source_api.openapi_url,
        root_path=root_path,
    )
    client = TestClient(app)
    response = client.get(root_path + source_api.openapi_url)
    assert response.status_code == 200
    openapi = response.json()
    assert "servers" in openapi
    assert openapi["servers"] == [{"url": root_path}]


def test_no_root_path_in_openapi_spec(source_api: FastAPI, source_api_server: str):
    """When root_path is not set, the OpenAPI spec does not include a servers field."""
    app = app_factory(
        upstream_url=source_api_server,
        openapi_spec_endpoint=source_api.openapi_url,
        root_path="",  # Empty string means no root path
    )
    client = TestClient(app)
    response = client.get(source_api.openapi_url)
    assert response.status_code == 200
    openapi = response.json()
    assert "servers" not in openapi
