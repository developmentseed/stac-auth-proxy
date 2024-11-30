"""Basic test cases for the proxy app."""

from fastapi.testclient import TestClient


def test_auth_applied(proxy_app):
    """Verify authentication is applied."""
    client = TestClient(proxy_app)
    response = client.get("/")
    assert response.status_code == 403, "Expect unauthorized without auth header"


def test_correct_auth_header(proxy_app):
    """Verify content is returned when correct auth header is provided."""
    client = TestClient(proxy_app)
    headers = {"Authorization": "Bearer correct_token"}
    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"message": "Hello from source API"}
