"""Test Cql2RewriteLinksFilterMiddleware."""

import json
import re

import pytest
from cql2 import Expr
from fastapi import FastAPI, Request, Response
from starlette.testclient import TestClient

from stac_auth_proxy.middleware.Cql2RewriteLinksFilterMiddleware import (
    Cql2RewriteLinksFilterMiddleware,
)


def _install_middlewares(app: FastAPI, system_filter: str) -> None:
    """Attach the rewrite middleware behind a mock build-filter middleware."""

    class MockBuildFilterMiddleware:
        def __init__(self, app, state_key="cql2_filter"):
            self.app = app
            self.state_key = state_key

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                request = Request(scope)
                setattr(request.state, self.state_key, Expr(system_filter))
            await self.app(scope, receive, send)

    app.add_middleware(Cql2RewriteLinksFilterMiddleware)
    app.add_middleware(MockBuildFilterMiddleware)


def test_non_json_response():
    """Test middleware behavior with non-JSON responses."""
    app = FastAPI()
    app.add_middleware(Cql2RewriteLinksFilterMiddleware)

    @app.get("/plain")
    async def plain():
        return Response(content="not json", media_type="text/plain")

    client = TestClient(app)
    response = client.get("/plain")
    assert response.status_code == 200
    assert response.text == "not json"


class TestEdgeCases:
    """Test middleware behavior with edge cases."""

    def test_no_links_in_response(self):
        """Test middleware behavior when response has no links."""
        app = FastAPI()
        app.add_middleware(Cql2RewriteLinksFilterMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request):
            return {"data": "no links here"}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        data = response.json()
        assert data == {"data": "no links here"}

    def test_malformed_json_response(self):
        """Test middleware behavior with malformed JSON response."""
        app = FastAPI()
        app.add_middleware(Cql2RewriteLinksFilterMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request):
            return Response(content="invalid json", media_type="application/json")

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert response.text == "invalid json"

    def test_links_not_list(self):
        """Test middleware behavior when links is not a list."""
        app = FastAPI()
        app.add_middleware(Cql2RewriteLinksFilterMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request):
            return {"links": "not a list"}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        data = response.json()
        assert data == {"links": "not a list"}


class TestMiddlewareStackSimulation:
    """Test middleware behavior by simulating the full middleware stack."""

    @pytest.mark.parametrize(
        "system_filter,user_filter,state_key",
        [
            # Test 1: Basic system filter removal
            (
                "private = false",
                "cloud_coverage < 50",
                "cql2_filter",
            ),
            # Test 2: Different system filter
            (
                "collection = 'landsat'",
                "datetime > '2023-01-01'",
                "cql2_filter",
            ),
            # Test 3: Custom state key
            (
                "access_level = 'public'",
                "quality > 0.8",
                "custom_filter",
            ),
            # Test 4: Complex system filter
            (
                "(private = false) and (status = 'active')",
                "cloud_coverage < 30",
                "cql2_filter",
            ),
            # Test 5: No user filter provided
            (
                "private = false",
                None,
                "cql2_filter",
            ),
            # Test 6: No user filter with different system filter
            (
                "collection = 'landsat'",
                None,
                "cql2_filter",
            ),
        ],
    )
    def test_middleware_removes_system_filter_from_query_string_links(
        self,
        system_filter,
        user_filter,
        state_key,
    ):
        """Test that middleware removes system-applied filter from query string links."""
        app = FastAPI()

        # Add a middleware that simulates Cql2BuildFilterMiddleware
        class MockBuildFilterMiddleware:
            def __init__(self, app, state_key="cql2_filter"):
                self.app = app
                self.state_key = state_key

            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    request = Request(scope)
                    setattr(request.state, self.state_key, Expr(system_filter))
                await self.app(scope, receive, send)

        app.add_middleware(Cql2RewriteLinksFilterMiddleware, state_key=state_key)
        app.add_middleware(MockBuildFilterMiddleware, state_key=state_key)

        @app.get("/test")
        async def test_endpoint(request: Request):
            # Automatically join system and user filters using CQL2 operators
            system_expr = getattr(request.state, state_key, None)
            user_filter_param = request.query_params.get("filter")

            # Build combined expression using CQL2 operators
            combined_expr = None
            if system_expr and user_filter_param:
                # Both system and user filters exist - join them with &
                user_expr = Expr(user_filter_param)
                combined_expr = system_expr + user_expr
            elif system_expr:
                # Only system filter exists
                combined_expr = system_expr
            elif user_filter_param:
                # Only user filter exists
                combined_expr = Expr(user_filter_param)

            filter_param = f"filter={combined_expr.to_text()}" if combined_expr else ""
            separator = "&" if filter_param else ""

            return {
                "links": [
                    {
                        "rel": "self",
                        "href": f"http://example.com/search?{filter_param}{separator}other=param",
                    }
                ]
            }

        # Build the request URL
        if user_filter:
            url = f"/test?filter={user_filter}"
        else:
            url = "/test"

        client = TestClient(app)
        response = client.get(url)
        assert response.status_code == 200
        data = response.json()

        # System filter should be removed, leaving only user filter
        href = data["links"][0]["href"]

        if user_filter:
            # When user filter exists, it should be present in the result
            assert "filter=" in href
            # Check that key terms from user filter are present
            user_expr = Expr(user_filter)
            user_text = user_expr.to_text()
            # Extract meaningful terms (skip operators and literals)
            user_terms = [
                term
                for term in re.findall(r"\b\w+\b", user_text)
                if term not in ["and", "or", "not", "true", "false"]
            ]
            for term in user_terms:
                assert term in href
        else:
            # When no user filter, the filter parameter should be completely removed
            assert "filter=" not in href

        # The system filter should NOT be in the result
        system_expr = Expr(system_filter)
        system_text = system_expr.to_text()
        # Extract meaningful terms from system filter
        system_terms = [
            term
            for term in re.findall(r"\b\w+\b", system_text)
            if term not in ["and", "or", "not", "true", "false"]
        ]
        for term in system_terms:
            assert term not in href

        # Other parameters should remain
        assert "other=param" in href

    @pytest.mark.parametrize(
        "system_filter,user_filter,expected_filter,state_key",
        [
            # Test 1: Basic request body filter removal
            (
                "private = false",
                "cloud_coverage < 50",
                {"op": "<", "args": [{"property": "cloud_coverage"}, 50]},
                "cql2_filter",
            ),
            # Test 2: Different system filter in body
            (
                "collection = 'landsat'",
                "datetime > '2023-01-01'",
                {"op": ">", "args": [{"property": "datetime"}, "2023-01-01"]},
                "cql2_filter",
            ),
            # Test 3: Custom state key
            (
                "access_level = 'public'",
                "quality > 0.8",
                {"op": ">", "args": [{"property": "quality"}, 0.8]},
                "custom_filter",
            ),
            # Test 4: No user filter provided
            (
                "private = false",
                None,
                None,  # Should be completely removed
                "cql2_filter",
            ),
        ],
    )
    def test_middleware_removes_system_filter_from_request_body_links(
        self, system_filter, user_filter, expected_filter, state_key
    ):
        """Test that middleware removes system filter from request body links."""
        app = FastAPI()

        class MockBuildFilterMiddleware:
            def __init__(self, app, state_key="cql2_filter"):
                self.app = app
                self.state_key = state_key

            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    request = Request(scope)
                    setattr(request.state, self.state_key, Expr(system_filter))
                await self.app(scope, receive, send)

        app.add_middleware(Cql2RewriteLinksFilterMiddleware, state_key=state_key)
        app.add_middleware(MockBuildFilterMiddleware, state_key=state_key)

        @app.get("/test")
        async def test_endpoint(request: Request):
            # Automatically create combined filter for request body using CQL2 operators
            system_expr = getattr(request.state, state_key, None)
            user_filter_param = request.query_params.get("filter")

            # Build combined expression using CQL2 operators
            combined_expr = None
            if system_expr and user_filter_param:
                # Both system and user filters exist - join them with &
                user_expr = Expr(user_filter_param)
                combined_expr = system_expr + user_expr
            elif system_expr:
                # Only system filter exists
                combined_expr = system_expr
            elif user_filter_param:
                # Only user filter exists
                combined_expr = Expr(user_filter_param)

            body_data = {
                "other_data": "preserved",
            }

            if combined_expr:
                body_data["filter"] = combined_expr.to_json()
                body_data["filter-lang"] = "cql2-json"

            return {
                "links": [
                    {
                        "rel": "post",
                        "body": body_data,
                    }
                ]
            }

        # Build the request URL
        if user_filter:
            url = f"/test?filter={user_filter}"
        else:
            url = "/test"

        client = TestClient(app)
        response = client.get(url)
        assert response.status_code == 200
        data = response.json()

        body = data["links"][0]["body"]

        if expected_filter:
            # System filter should be removed from request body, leaving only user filter
            assert body["filter"] == expected_filter
            # filter-lang should remain since there's still a filter
            assert body["filter-lang"] == "cql2-json"
        else:
            # When no user filter, the filter should be completely removed
            assert "filter" not in body
            assert "filter-lang" not in body

        # Other data should be preserved
        assert body["other_data"] == "preserved"


class TestPostBodyClientFilterPreservation:
    """
    Client filters sent in a POST search body must be preserved in next-link bodies.

    Regression: the middleware previously read the user's filter only from the
    query string, silently dropping filters supplied via POST body.
    """

    @pytest.mark.parametrize(
        "client_filter,client_filter_lang",
        [
            (
                {"op": "<", "args": [{"property": "cloud_coverage"}, 50]},
                "cql2-json",
            ),
            ("cloud_coverage < 30", "cql2-text"),
            (None, None),
        ],
    )
    def test_preserves_client_filter_from_post_body(
        self, client_filter, client_filter_lang
    ):
        """Filter supplied in the POST body must be preserved in the next link."""
        app = FastAPI()
        _install_middlewares(app, system_filter="private = false")

        @app.post("/search")
        async def search_endpoint(request: Request):
            body_json = await request.json()
            system_expr = getattr(request.state, "cql2_filter", None)
            user_filter = body_json.get("filter")
            user_filter_lang = body_json.get("filter-lang")

            combined = None
            if system_expr is not None and user_filter is not None:
                combined = system_expr + Expr(user_filter)
            elif system_expr is not None:
                combined = system_expr
            elif user_filter is not None:
                combined = Expr(user_filter)

            next_body = {"token": "next-token"}
            if combined is not None:
                lang = user_filter_lang or "cql2-json"
                next_body["filter-lang"] = lang
                next_body["filter"] = (
                    combined.to_text() if lang == "cql2-text" else combined.to_json()
                )

            return {
                "links": [
                    {
                        "rel": "next",
                        "method": "POST",
                        "href": "http://example.com/search",
                        "body": next_body,
                    }
                ],
            }

        request_body = {}
        if client_filter is not None:
            request_body["filter"] = client_filter
            request_body["filter-lang"] = client_filter_lang

        response = TestClient(app).post("/search", json=request_body)
        assert response.status_code == 200, response.text
        body = response.json()["links"][0]["body"]

        assert body["token"] == "next-token"

        if client_filter is None:
            # No client filter → system filter must not leak into next link.
            assert "filter" not in body
            assert "filter-lang" not in body
        else:
            # Compare semantically: cql2-python may re-emit equivalent text
            # with different formatting (e.g. added parens).
            assert Expr(body["filter"]).to_json() == Expr(client_filter).to_json()
            assert body["filter-lang"] == client_filter_lang

    def test_request_body_is_intact_for_inner_app(self):
        """Body capture must replay the exact original bytes to the inner app."""
        app = FastAPI()
        _install_middlewares(app, system_filter="private = false")

        @app.post("/search")
        async def search_endpoint(request: Request):
            return {"echo": json.loads(await request.body())}

        request_body = {
            "collections": ["a", "b"],
            "filter": {"op": "=", "args": [{"property": "x"}, 1]},
            "filter-lang": "cql2-json",
        }
        response = TestClient(app).post("/search", json=request_body)
        assert response.status_code == 200, response.text
        assert response.json()["echo"] == request_body

    def test_malformed_json_body_does_not_break_middleware(self):
        """An unparseable body must pass through without the middleware crashing."""
        app = FastAPI()
        _install_middlewares(app, system_filter="private = false")

        @app.post("/search")
        async def search_endpoint(request: Request):
            return Response(
                content=await request.body(),
                media_type="application/octet-stream",
            )

        response = TestClient(app).post(
            "/search",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 200
        assert response.content == b"not json"
