import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stac_auth_proxy import Settings, create_app


def test_no_edit_openapi_spec(source_api_server):
    """
    When no OpenAPI spec endpoint is set, the proxied OpenAPI spec is unaltered.
    """
    app = create_app(
        Settings(
            upstream_url=source_api_server,
            oidc_discovery_url="https://samples.auth0.com/.well-known/openid-configuration",
        )
    )
    client = TestClient(app)
    response = client.get("/api")
    assert response.status_code == 200
    openapi = response.json()
    assert "info" in openapi
    assert "openapi" in openapi
    assert "paths" in openapi
    assert "oidcAuth" not in openapi.get("components", {}).get("securitySchemes", {})


# @pytest.mark.skip(reason="This test is failing")
def test_oidc_in_openapi_spec(source_api: FastAPI, source_api_server: str):
    """
    When OpenAPI spec endpoint is set, the proxied OpenAPI spec is augmented with oidc details.
    """
    app = create_app(
        Settings(
            upstream_url=source_api_server,
            oidc_discovery_url="https://samples.auth0.com/.well-known/openid-configuration",
            openapi_spec_endpoint=source_api.openapi_url,
        )
    )
    print(f"{source_api.openapi_url=}")
    client = TestClient(app)
    response = client.get(source_api.openapi_url)
    assert response.status_code == 200
    openapi = response.json()
    assert "info" in openapi
    assert "openapi" in openapi
    assert "paths" in openapi
    assert "oidcAuth" in openapi.get("components", {}).get("securitySchemes", {})
