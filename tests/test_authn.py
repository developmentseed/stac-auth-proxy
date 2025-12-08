"""Test authentication cases for the proxy app."""

import pytest
from fastapi.testclient import TestClient
from utils import AppFactory

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
    default_public=False,
    public_endpoints={},
    private_endpoints={},
)


@pytest.mark.parametrize(
    "path,method",
    [
        ("/", "GET"),
        ("/conformance", "GET"),
        ("/queryables", "GET"),
        ("/search", "GET"),
        ("/search", "POST"),
        ("/collections", "GET"),
        ("/collections", "POST"),
        ("/collections/example-collection", "GET"),
        ("/collections/example-collection", "PUT"),
        ("/collections/example-collection", "DELETE"),
        ("/collections/example-collection/items", "GET"),
        ("/collections/example-collection/items", "POST"),
        ("/collections/example-collection/items/example-item", "GET"),
        ("/collections/example-collection/items/example-item", "PUT"),
        ("/collections/example-collection/items/example-item", "DELETE"),
        ("/collections/example-collection/bulk_items", "POST"),
        ("/api.html", "GET"),
        ("/api", "GET"),
    ],
)
def test_default_public_false(source_api_server, path, method, token_builder):
    """Private endpoints require authentication and return 401 when not authenticated."""
    test_app = app_factory(upstream_url=source_api_server)
    valid_auth_token = token_builder({})

    client = TestClient(test_app)
    response = client.request(method=method, url=path, headers={})
    assert response.status_code == 401  # Not authenticated -> 401

    response = client.request(
        method=method, url=path, headers={"Authorization": f"Bearer {valid_auth_token}"}
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "rules,token,permitted",
    [
        [
            [("POST", "collection:create")],
            {"scope": "collection:create"},
            True,
        ],
        [
            [("POST", "collection:create")],
            {"scope": ""},
            False,
        ],
        [
            [("POST", "collection:create")],
            {"scope": "openid"},
            False,
        ],
        [
            [("POST", "collection:create")],
            {"scope": "openid collection:create"},
            True,
        ],
        [
            [("POST", "foo collection:create")],
            {"scope": "openid collection:create foo"},
            True,
        ],
        [
            [("GET", "collection:read"), ("POST", "collection:create")],
            {"scope": "openid collection:read"},
            False,
        ],
    ],
)
def test_default_public_false_with_scopes(
    source_api_server, rules, token, permitted, token_builder
):
    """Private endpoints permit access with valid token AND required scopes."""
    test_app = app_factory(
        upstream_url=source_api_server,
        default_public=False,
        private_endpoints={r"^/collections$": rules},
    )
    valid_auth_token = token_builder(token)

    client = TestClient(test_app)
    response = client.request(
        method="POST",
        url="/collections",
        headers={"Authorization": f"Bearer {valid_auth_token}"},
    )
    # Authenticated but lacking scopes -> 403, not 401
    assert response.status_code == (200 if permitted else 403)


@pytest.mark.parametrize(
    "token_scopes, private_endpoints, path, method, expected_permitted",
    [
        pytest.param(
            "",
            {r"^/*": [("POST", "collection:create")]},
            "/collections",
            "POST",
            False,
            id="empty scopes + private endpoint",
        ),
        pytest.param(
            "openid profile collection:createbutnotcreate",
            {r"^/*": [("POST", "collection:create")]},
            "/collections",
            "POST",
            False,
            id="invalid scopes + private endpoint",
        ),
        pytest.param(
            "openid profile collection:create somethingelse",
            {r"^/*": [("POST", "")]},
            "/collections",
            "POST",
            True,
            id="valid scopes + private endpoint without required scopes",
        ),
        pytest.param(
            "openid",
            {r"^/collections/.*/items$": [("POST", "collection:create")]},
            "/collections",
            "GET",
            True,
            id="accessing public endpoint with private endpoint required scopes",
        ),
    ],
)
def test_scopes(
    source_api_server,
    token_builder,
    token_scopes,
    private_endpoints,
    path,
    method,
    expected_permitted,
):
    """Private endpoints require valid token AND required scopes."""
    test_app = app_factory(
        upstream_url=source_api_server,
        default_public=True,
        private_endpoints=private_endpoints,
    )
    valid_auth_token = token_builder({"scope": token_scopes})
    client = TestClient(test_app)

    response = client.request(
        method=method,
        url=path,
        headers={"Authorization": f"Bearer {valid_auth_token}"},
    )
    # User is authenticated, so insufficient scopes -> 403, not 401
    expected_status_code = 200 if expected_permitted else 403
    assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "path,default_public,private_endpoints",
    [
        ("/", False, {}),
        ("/collections", False, {}),
        ("/search", False, {}),
        ("/collections", True, {r"^/collections$": [("POST", "collection:create")]}),
        ("/search", True, {r"^/search$": [("POST", "search:write")]}),
        (
            "/collections/example-collection/items",
            True,
            {r"^/collections/.*/items$": [("POST", "item:create")]},
        ),
    ],
)
def test_options_bypass_auth(
    path, default_public, private_endpoints, source_api_server
):
    """OPTIONS requests should bypass authentication regardless of endpoint configuration."""
    test_app = app_factory(
        upstream_url=source_api_server,
        default_public=default_public,
        private_endpoints=private_endpoints,
    )
    client = TestClient(test_app)
    response = client.options(path)
    assert response.status_code == 200, "OPTIONS request should bypass authentication"


@pytest.mark.parametrize(
    "path,method,default_public,private_endpoints,expected_status",
    [
        # Test that non-OPTIONS requests return 401 when not authenticated
        ("/collections", "GET", False, {}, 401),
        ("/collections", "POST", False, {}, 401),
        ("/search", "GET", False, {}, 401),
        # Test that OPTIONS requests bypass auth even when endpoints are private
        ("/collections", "OPTIONS", False, {}, 200),
        ("/search", "OPTIONS", False, {}, 200),
        # Test with specific private endpoint configurations
        (
            "/collections",
            "POST",
            True,
            {r"^/collections$": [("POST", "collection:create")]},
            401,
        ),
        (
            "/collections",
            "OPTIONS",
            True,
            {r"^/collections$": [("POST", "collection:create")]},
            200,
        ),
    ],
)
def test_options_vs_other_methods_auth_behavior(
    path, method, default_public, private_endpoints, expected_status, source_api_server
):
    """Compare authentication behavior between OPTIONS and other HTTP methods."""
    test_app = app_factory(
        upstream_url=source_api_server,
        default_public=default_public,
        private_endpoints=private_endpoints,
    )
    client = TestClient(test_app)
    response = client.request(method=method, url=path, headers={})
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "path,method,default_public,private_endpoints,expected_status",
    [
        # Test that requests with valid auth succeed
        ("/collections", "GET", False, {}, 200),
        ("/collections", "POST", False, {}, 200),
        ("/search", "GET", False, {}, 200),
        ("/collections", "OPTIONS", False, {}, 200),
        ("/search", "OPTIONS", False, {}, 200),
        # Test with specific private endpoint configurations
        (
            "/collections",
            "POST",
            True,
            {r"^/collections$": [("POST", "collection:create")]},
            200,
        ),
        (
            "/collections",
            "OPTIONS",
            True,
            {r"^/collections$": [("POST", "collection:create")]},
            200,
        ),
    ],
)
def test_options_vs_other_methods_with_valid_auth(
    path,
    method,
    default_public,
    private_endpoints,
    expected_status,
    source_api_server,
    token_builder,
):
    """Compare authentication behavior between OPTIONS and other HTTP methods with valid auth."""
    test_app = app_factory(
        upstream_url=source_api_server,
        default_public=default_public,
        private_endpoints=private_endpoints,
    )
    valid_auth_token = token_builder({"scope": "collection:create"})
    client = TestClient(test_app)
    response = client.request(
        method=method,
        url=path,
        headers={"Authorization": f"Bearer {valid_auth_token}"},
    )
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "invalid_token,expected_status",
    [
        ("Bearer invalid-token", 401),
        (
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
            401,
        ),
        ("InvalidFormat", 401),
        ("Bearer", 401),
        ("", 401),  # No auth header returns 401 (not authenticated)
    ],
)
def test_with_invalid_tokens_fails(invalid_token, expected_status, source_api_server):
    """GET requests should fail with invalid or malformed tokens."""
    test_app = app_factory(
        upstream_url=source_api_server,
        default_public=False,  # All endpoints private
        private_endpoints={},
    )
    client = TestClient(test_app)
    response = client.get("/collections", headers={"Authorization": invalid_token})
    assert response.status_code == expected_status, (
        f"GET request should fail with token: {invalid_token}"
    )

    response = client.options("/collections", headers={"Authorization": invalid_token})
    assert response.status_code == 200, (
        f"OPTIONS request should succeed with token: {invalid_token}"
    )


def test_options_requests_with_cors_headers(source_api_server):
    """OPTIONS requests should work properly with CORS headers."""
    test_app = app_factory(
        upstream_url=source_api_server,
        default_public=False,  # All endpoints private
        private_endpoints={},
    )
    client = TestClient(test_app)

    # Test OPTIONS request with CORS headers
    cors_headers = {
        "Origin": "https://example.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type,Authorization",
    }

    response = client.options("/collections", headers=cors_headers)
    assert response.status_code == 200, (
        "OPTIONS request with CORS headers should succeed"
    )


@pytest.mark.parametrize(
    "token_audiences,allowed_audiences,expected_status",
    [
        # Single audience scenarios
        (["stac-api"], "stac-api", 200),
        (["stac-api"], "different-api", 401),
        (["stac-api"], "stac-api,other-api", 200),
        # Multiple audiences in token
        (["stac-api", "other-api"], "stac-api", 200),
        (["stac-api", "other-api"], "other-api", 200),
        (["stac-api", "other-api"], "different-api", 401),
        (["stac-api", "other-api"], "stac-api, other-api,third-api", 200),
        # No audience in token
        (None, "stac-api", 401),
        ("", "stac-api", 401),
        # Empty allowed audiences will regect tokens with an `aud` claim
        ("any-api", "", 401),
        ("any-api", None, 401),
        # Backward compatibility - no audience configured
        (None, None, 200),
        ("", None, 200),
    ],
)
def test_jwt_audience_validation(
    source_api_server,
    token_builder,
    token_audiences,
    allowed_audiences,
    expected_status,
):
    """Test JWT audience validation with various configurations."""
    # Build app with audience configuration
    app_factory = AppFactory(
        oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
        default_public=False,
        allowed_jwt_audiences=allowed_audiences,
    )
    test_app = app_factory(upstream_url=source_api_server)

    # Build token with audience claim
    token_payload = {}
    if token_audiences is not None:
        token_payload["aud"] = token_audiences

    valid_auth_token = token_builder(token_payload)

    client = TestClient(test_app)
    response = client.get(
        "/collections",
        headers={"Authorization": f"Bearer {valid_auth_token}"},
    )
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "aud_value,scope,expected_status,description",
    [
        (
            ["stac-api"],
            "openid",
            403,
            "Valid audience but missing scope (authenticated but not authorized)",
        ),
        (["stac-api"], "collection:create", 200, "Valid audience and valid scope"),
        (
            ["wrong-api"],
            "collection:create",
            401,
            "Invalid audience but valid scope (authentication failed)",
        ),
    ],
)
def test_audience_validation_with_scopes(
    source_api_server, token_builder, aud_value, scope, expected_status, description
):
    """Test that audience validation works alongside scope validation."""
    app_factory = AppFactory(
        oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
        default_public=False,
        allowed_jwt_audiences="stac-api",
        private_endpoints={r"^/collections$": [("POST", "collection:create")]},
    )
    test_app = app_factory(upstream_url=source_api_server)

    client = TestClient(test_app)

    token = token_builder({"aud": aud_value, "scope": scope})
    response = client.post(
        "/collections",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "allowed_audiences_config,test_audience,expected_status",
    [
        # Comma-separated string
        ("stac-api,other-api", "stac-api", 200),
        ("stac-api,other-api", "other-api", 200),
        ("stac-api,other-api", "unknown-api", 401),
        # Comma-separated with spaces
        ("stac-api, other-api", "stac-api", 200),
        ("stac-api, other-api", "other-api", 200),
        ("stac-api, other-api", "unknown-api", 401),
    ],
)
def test_allowed_audiences_configuration_formats(
    source_api_server,
    token_builder,
    allowed_audiences_config,
    test_audience,
    expected_status,
):
    """Test different configuration formats for ALLOWED_JWT_AUDIENCES."""
    app_factory = AppFactory(
        oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
        default_public=False,
        allowed_jwt_audiences=allowed_audiences_config,
    )
    test_app = app_factory(upstream_url=source_api_server)

    client = TestClient(test_app)

    token = token_builder({"aud": [test_audience]})
    response = client.get(
        "/collections",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == expected_status
