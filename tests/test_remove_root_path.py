"""Tests for RemoveRootPathMiddleware."""

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send

from stac_auth_proxy.middleware.RemoveRootPathMiddleware import RemoveRootPathMiddleware


class MockASGIApp:
    """Mock ASGI application for testing."""

    def __init__(self):
        """Initialize the mock app."""
        self.called = False
        self.scope = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Mock ASGI call."""
        self.called = True
        self.scope = scope


@pytest.mark.asyncio
async def test_remove_root_path_middleware():
    """Test that root path is removed from request path."""
    mock_app = MockASGIApp()
    middleware = RemoveRootPathMiddleware(mock_app, root_path="/api")

    # Test with root path
    scope = {
        "type": "http",
        "path": "/api/test",
        "raw_path": b"/api/test",
    }
    await middleware(scope, None, None)
    assert mock_app.called
    assert mock_app.scope["path"] == "/test"
    assert mock_app.scope["raw_path"] == b"/api/test"


@pytest.mark.asyncio
async def test_remove_root_path_middleware_non_http():
    """Test that non-HTTP requests are passed through unchanged."""
    mock_app = MockASGIApp()
    middleware = RemoveRootPathMiddleware(mock_app, root_path="/api")

    scope = {
        "type": "websocket",
        "path": "/api/test",
    }
    await middleware(scope, None, None)
    assert mock_app.called
    assert mock_app.scope["path"] == "/api/test"


@pytest.mark.asyncio
async def test_remove_root_path_middleware_empty_path():
    """Test that empty path after root path removal is set to '/'."""
    mock_app = MockASGIApp()
    middleware = RemoveRootPathMiddleware(mock_app, root_path="/api")

    scope = {
        "type": "http",
        "path": "/api",
        "raw_path": b"/api",
    }
    await middleware(scope, None, None)
    assert mock_app.called
    assert mock_app.scope["path"] == "/"
    assert mock_app.scope["raw_path"] == b"/api"


def test_remove_root_path_middleware_integration():
    """Test middleware integration with FastAPI."""
    app = FastAPI()
    app.add_middleware(RemoveRootPathMiddleware, root_path="/api")

    @app.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    client = TestClient(app)

    # Test with root path
    response = client.get("/api/test")
    assert response.status_code == 200
    assert response.json() == {"message": "test"}

    # Test without root path
    response = client.get("/test")
    assert response.status_code == 404  # Should not find the endpoint
