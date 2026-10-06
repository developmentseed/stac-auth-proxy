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


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api../test", "/apitest", "/ap"])
async def test_remove_root_path_middleware_segment_boundary(path):
    """Paths that only share a string prefix with root_path are not under it."""
    mock_app = MockASGIApp()
    middleware = RemoveRootPathMiddleware(mock_app, root_path="/api")
    sent = []

    async def send(message):
        sent.append(message)

    await middleware(
        {"type": "http", "path": path, "raw_path": path.encode()}, None, send
    )
    assert not mock_app.called
    assert sent[0]["status"] == 404


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


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/api/test", "/api/api"])
async def test_remove_root_path_middleware_rejects_path_app_would_strip_again(path):
    """Reject paths that the app's router would strip scope["root_path"] from again."""
    mock_app = MockASGIApp()
    middleware = RemoveRootPathMiddleware(mock_app, root_path="/api")
    sent = []

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "/api",
        "headers": [],
    }
    await middleware(scope, None, send)
    assert not mock_app.called
    assert sent[0]["status"] == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "root_path"),
    [
        ("/api/test", "/api"),  # app root_path matches, stripped path routes as-is
        ("/api/apiary", "/api"),  # not a path-segment match
    ],
)
async def test_remove_root_path_middleware_allows_unambiguous_paths(path, root_path):
    """Paths the router would not strip again are passed through."""
    mock_app = MockASGIApp()
    middleware = RemoveRootPathMiddleware(mock_app, root_path="/api")
    scope = {
        "type": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": root_path,
    }
    await middleware(scope, None, None)
    assert mock_app.called
    assert mock_app.scope["path"] == path[len("/api") :]


def test_remove_root_path_middleware_trailing_slash_root_path():
    """A root path given with a trailing slash is normalized, as Settings does."""
    app = FastAPI()

    @app.get("/collections")
    async def collections():
        return {"ok": True}

    app.add_middleware(RemoveRootPathMiddleware, root_path="/stac/")
    assert TestClient(app).get("/stac/collections").json() == {"ok": True}


@pytest.mark.asyncio
async def test_remove_root_path_middleware_rejects_doubled_root_path_without_app_root():
    """
    "/api/api/x" is checked as "/api/x" even when the app has no root path of its
    own: an upstream sharing ROOT_PATH would remove "/api" again, so reject it.
    """
    mock_app = MockASGIApp()
    middleware = RemoveRootPathMiddleware(mock_app, root_path="/api")
    sent = []

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "path": "/api/api/x", "raw_path": b"/api/api/x"}
    await middleware(scope, None, send)
    assert not mock_app.called
    assert sent[0]["status"] == 404
