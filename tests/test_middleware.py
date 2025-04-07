"""Tests for middleware utilities."""

from typing import Any

from fastapi import FastAPI, Response
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.testclient import TestClient
from starlette.types import ASGIApp, Scope

from stac_auth_proxy.utils.middleware import JsonResponseMiddleware


class ExampleJsonResponseMiddleware(JsonResponseMiddleware):
    """Example implementation of JsonResponseMiddleware."""

    def __init__(self, app: ASGIApp):
        """Initialize the middleware."""
        self.app = app

    def should_transform_response(self, request: Request, scope: Scope) -> bool:
        """Transform JSON responses based on content type."""
        return Headers(scope=scope).get("content-type", "") == "application/json"

    def transform_json(self, data: Any, request: Request) -> Any:
        """Add a test field to the response."""
        if isinstance(data, dict):
            data["transformed"] = True
        return data


def test_json_response_middleware():
    """Test that JSON responses are properly transformed."""
    app = FastAPI()
    app.add_middleware(ExampleJsonResponseMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert data["message"] == "test"
    assert data["transformed"] is True


def test_json_response_middleware_no_transform():
    """Test that responses are not transformed when should_transform_response returns False."""
    app = FastAPI()
    app.add_middleware(ExampleJsonResponseMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return Response(
            content='{"message": "test"}',
            media_type="application/x-json",  # Different from application/json
        )

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200
    assert "application/x-json" in response.headers["content-type"]
    data = response.json()
    assert data["message"] == "test"
    assert "transformed" not in data


def test_json_response_middleware_chunked():
    """Test that chunked JSON responses are properly transformed."""
    app = FastAPI()
    app.add_middleware(ExampleJsonResponseMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"message": "test", "large_field": "x" * 10000}

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert data["message"] == "test"
    assert data["transformed"] is True
    assert len(data["large_field"]) == 10000


def test_json_response_middleware_error_handling():
    """Test that JSON parsing errors are handled gracefully."""
    app = FastAPI()
    app.add_middleware(ExampleJsonResponseMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return Response(content="invalid json", media_type="text/plain")

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert response.text == "invalid json"
