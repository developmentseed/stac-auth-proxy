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
    public = {r"^/queryables$": ["GET"], r"^/api$": ["GET"]}
    app = app_factory(
        upstream_url=source_api_server,
        openapi_spec_endpoint=source_api.openapi_url,
        default_public=False,
        public_endpoints=public,
    )
    client = TestClient(app)

    openapi = client.get(source_api.openapi_url).raise_for_status().json()

    expected_required_auth = {"/queryables": ["GET"]}
    for path, method_config in openapi["paths"].items():
        for method, config in method_config.items():
            security = config.get("security")

            if method == "options":
                assert not security, (
                    f"OPTIONS {path} requests should not require authentication"
                )
                continue

            if security:
                assert path not in expected_required_auth, (
                    f"Path {path} should not require authentication"
                )
                continue

            assert path in expected_required_auth, (
                f"Path {path} should require authentication"
            )
            assert any(
                method.casefold() == m.casefold() for m in expected_required_auth[path]
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


def test_upstream_servers_removed_when_root_path_set(
    source_api: FastAPI, source_api_server: str, source_api_responses
):
    """When upstream API has servers field and proxy has root_path, upstream servers are removed and replaced with proxy servers."""
    # Configure upstream API to return a servers field
    upstream_servers = [{"url": "https://upstream-api.com/stage"}]
    # Add the /api endpoint to the responses
    source_api_responses["/api"] = {
        "GET": {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {},
            "servers": upstream_servers,
        }
    }

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

    # Verify upstream servers are removed and replaced with proxy servers
    assert "servers" in openapi
    assert openapi["servers"] == [{"url": root_path}]
    assert openapi["servers"] != upstream_servers


def test_upstream_servers_removed_when_no_root_path(
    source_api: FastAPI, source_api_server: str, source_api_responses
):
    """When upstream API has servers field and proxy has no root_path, upstream servers are removed and no servers field is added."""
    # Configure upstream API to return a servers field
    upstream_servers = [{"url": "https://upstream-api.com/stage"}]
    # Add the /api endpoint to the responses
    source_api_responses["/api"] = {
        "GET": {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {},
            "servers": upstream_servers,
        }
    }

    app = app_factory(
        upstream_url=source_api_server,
        openapi_spec_endpoint=source_api.openapi_url,
        root_path="",  # No root path
    )
    client = TestClient(app)
    response = client.get(source_api.openapi_url)
    assert response.status_code == 200
    openapi = response.json()

    # Verify upstream servers are removed and no servers field is added
    assert "servers" not in openapi


def test_no_servers_field_when_upstream_has_none(
    source_api: FastAPI, source_api_server: str, source_api_responses
):
    """When upstream API has no servers field and proxy has no root_path, no servers field is added."""
    # Configure upstream API to return no servers field
    source_api_responses["/api"] = {
        "GET": {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {},
            # No servers field
        }
    }

    app = app_factory(
        upstream_url=source_api_server,
        openapi_spec_endpoint=source_api.openapi_url,
        root_path="",  # No root path
    )
    client = TestClient(app)
    response = client.get(source_api.openapi_url)
    assert response.status_code == 200
    openapi = response.json()

    # Verify no servers field is added
    assert "servers" not in openapi


def test_multiple_upstream_servers_removed(
    source_api: FastAPI, source_api_server: str, source_api_responses
):
    """When upstream API has multiple servers, all are removed and replaced with proxy server."""
    # Configure upstream API to return multiple servers
    upstream_servers = [
        {"url": "https://upstream-api.com/stage"},
        {"url": "https://upstream-api.com/prod"},
        {
            "url": "https://staging.upstream-api.com",
            "description": "Staging environment",
        },
    ]
    source_api_responses["/api"] = {
        "GET": {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {},
            "servers": upstream_servers,
        }
    }

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

    # Verify all upstream servers are removed and replaced with proxy server
    assert "servers" in openapi
    assert openapi["servers"] == [{"url": root_path}]
    assert len(openapi["servers"]) == 1
    assert openapi["servers"] != upstream_servers


def test_upstream_servers_with_variables_removed(
    source_api: FastAPI, source_api_server: str, source_api_responses
):
    """When upstream API has servers with variables, they are removed and replaced with proxy server."""
    # Configure upstream API to return servers with variables
    upstream_servers = [
        {
            "url": "https://{environment}.upstream-api.com/{version}",
            "variables": {
                "environment": {"default": "prod", "enum": ["dev", "staging", "prod"]},
                "version": {"default": "v1", "enum": ["v1", "v2"]},
            },
        }
    ]
    source_api_responses["/api"] = {
        "GET": {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {},
            "servers": upstream_servers,
        }
    }

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

    # Verify upstream servers with variables are removed and replaced with proxy server
    assert "servers" in openapi
    assert openapi["servers"] == [{"url": root_path}]
    assert len(openapi["servers"]) == 1
    assert openapi["servers"] != upstream_servers


def test_malformed_servers_field_handled(
    source_api: FastAPI, source_api_server: str, source_api_responses
):
    """When upstream API has malformed servers field, it is removed and replaced with proxy server."""
    # Configure upstream API to return malformed servers field
    source_api_responses["/api"] = {
        "GET": {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {},
            "servers": "invalid_servers_field",  # Should be a list
        }
    }

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

    # Verify malformed servers field is removed and replaced with proxy server
    assert "servers" in openapi
    assert openapi["servers"] == [{"url": root_path}]
    assert isinstance(openapi["servers"], list)


def test_empty_servers_list_removed(
    source_api: FastAPI, source_api_server: str, source_api_responses
):
    """When upstream API has empty servers list, it is removed and replaced with proxy server."""
    # Configure upstream API to return empty servers list
    source_api_responses["/api"] = {
        "GET": {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {},
            "servers": [],  # Empty list
        }
    }

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

    # Verify empty servers list is removed and replaced with proxy server
    assert "servers" in openapi
    assert openapi["servers"] == [{"url": root_path}]
    assert len(openapi["servers"]) == 1


@pytest.mark.parametrize("root_path", [None, "/api/v1"])
def test_servers_are_replaced_with_proxy_server(root_path: str):
    """Test that verifies upstream servers are replaced with proxy server."""
    from unittest.mock import Mock

    from stac_auth_proxy.middleware.UpdateOpenApiMiddleware import OpenApiMiddleware

    # Test data with upstream servers
    test_data = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {},
        "servers": [
            {"url": "https://upstream-api.com/stage"},
            {"url": "https://upstream-api.com/prod"},
        ],
    }

    # Create middleware instance
    middleware = OpenApiMiddleware(
        app=Mock(),
        openapi_spec_path="/api",
        oidc_discovery_url="https://example.com/.well-known/openid-configuration",
        private_endpoints={},
        public_endpoints={},
        default_public=True,
        root_path=root_path,
    )

    # Test the middleware behavior
    result = middleware.transform_json(test_data.copy(), Mock())

    # Verify that only the proxy server remains
    if root_path:
        assert "servers" in result
        assert len(result["servers"]) == 1
        assert result["servers"][0]["url"] == root_path
    else:
        assert "servers" not in result

    # Verify upstream servers are gone
    for server in test_data["servers"]:
        assert server not in result.get("servers", [])
