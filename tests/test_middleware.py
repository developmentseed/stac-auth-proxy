"""Tests for middleware utilities."""

from typing import Any
from unittest.mock import patch

import pytest
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
        # Use default expected_data_type (dict)

    def should_transform_response(self, request: Request, scope: Scope) -> bool:
        """Transform JSON responses based on content type."""
        return Headers(scope=scope).get("content-type", "") == "application/json"

    def transform_json(self, data: Any, request: Request) -> Any:
        """Add a test field to the response."""
        data["transformed"] = True
        return data


class ExampleStringJsonResponseMiddleware(JsonResponseMiddleware):
    """Example implementation that expects string JSON responses."""

    def __init__(self, app: ASGIApp):
        """Initialize the middleware."""
        self.app = app
        self.expected_data_type = str

    def should_transform_response(self, request: Request, scope: Scope) -> bool:
        """Transform JSON responses based on content type."""
        return Headers(scope=scope).get("content-type", "") == "application/json"

    def transform_json(self, data: Any, request: Request) -> Any:
        """Transform string responses by adding a prefix."""
        if isinstance(data, str):
            return f"transformed: {data}"
        return data


class ExampleListJsonResponseMiddleware(JsonResponseMiddleware):
    """Example implementation that expects list JSON responses."""

    def __init__(self, app: ASGIApp):
        """Initialize the middleware."""
        self.app = app
        self.expected_data_type = list

    def should_transform_response(self, request: Request, scope: Scope) -> bool:
        """Transform JSON responses based on content type."""
        return Headers(scope=scope).get("content-type", "") == "application/json"

    def transform_json(self, data: Any, request: Request) -> Any:
        """Transform list responses by adding a new item."""
        if isinstance(data, list):
            return data + ["transformed"]
        return data


class ExampleAnyJsonResponseMiddleware(JsonResponseMiddleware):
    """Example implementation that transforms any JSON response type."""

    def __init__(self, app: ASGIApp):
        """Initialize the middleware."""
        self.app = app
        self.expected_data_type = None  # Transform any JSON type

    def should_transform_response(self, request: Request, scope: Scope) -> bool:
        """Transform JSON responses based on content type."""
        return Headers(scope=scope).get("content-type", "") == "application/json"

    def transform_json(self, data: Any, request: Request) -> Any:
        """Transform any JSON response by wrapping it."""
        return {"transformed": True, "data": data}


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


def test_json_response_middleware_invalid_json_upstream():
    """Test that invalid JSON from upstream server returns 502 error."""
    app = FastAPI()
    app.add_middleware(ExampleJsonResponseMiddleware)

    @app.get("/test")
    async def test_endpoint():
        # Return invalid JSON with JSON content type to trigger the error handling
        return Response(content="invalid json content", media_type="application/json")

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 502
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert data == {"error": "Received invalid JSON from upstream server"}


@pytest.mark.parametrize(
    "content,expected_data",
    [
        ('"hello world"', "hello world"),
        ('[1, 2, 3, "test"]', [1, 2, 3, "test"]),
        ("42", 42),
        ("true", True),
        ("null", None),
    ],
)
def test_json_response_middleware_non_dict_json(content, expected_data):
    """Test that non-dict JSON responses are not transformed by default middleware."""
    app = FastAPI()
    app.add_middleware(ExampleJsonResponseMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return Response(content=content, media_type="application/json")

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert data == expected_data  # Should remain unchanged


@pytest.mark.parametrize(
    "middleware_class, test_data, expected_result, should_transform",
    [
        # String middleware tests
        (
            ExampleStringJsonResponseMiddleware,
            "this is a string",
            "transformed: this is a string",
            True,
        ),
        (
            ExampleStringJsonResponseMiddleware,
            {"message": "not a string"},
            {"message": "not a string"},
            False,
        ),
        # List middleware tests
        (
            ExampleListJsonResponseMiddleware,
            [1, 2, 3],
            [1, 2, 3, "transformed"],
            True,
        ),
        (
            ExampleListJsonResponseMiddleware,
            "not a list",
            "not a list",
            False,
        ),
        # Dict middleware tests (default)
        (
            ExampleJsonResponseMiddleware,
            {"message": "test"},
            {"message": "test", "transformed": True},
            True,
        ),
        (
            ExampleJsonResponseMiddleware,
            "not a dict",
            "not a dict",
            False,
        ),
    ],
)
def test_json_response_middleware_type_specific(
    middleware_class, test_data, expected_result, should_transform
):
    """Test that middleware transforms only expected data types."""
    with patch.object(
        middleware_class, "transform_json", return_value=expected_result
    ) as mock_method:
        app = FastAPI()
        app.add_middleware(middleware_class)

        @app.get("/test")
        async def test_endpoint():
            return test_data

        client = TestClient(app)
        response = client.get("/test")

    data = response.json()
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert mock_method.call_count == (1 if should_transform else 0)
    if should_transform:
        assert mock_method.call_args[0][0] == test_data
    assert data == expected_result


@pytest.mark.parametrize(
    "test_data",
    [
        {"message": "test"},
        "hello world",
        [1, 2, 3],
        42,
        True,
        None,
    ],
)
def test_json_response_middleware_expected_none_type(test_data):
    """Test that middleware with expected_data_type=None transforms all JSON response types."""
    app = FastAPI()
    app.add_middleware(ExampleAnyJsonResponseMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return test_data

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()

    # Verify the simplified transformation behavior
    assert data["transformed"] is True
    assert data["data"] == test_data
