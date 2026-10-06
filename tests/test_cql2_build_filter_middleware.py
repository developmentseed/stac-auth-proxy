"""Test Cql2BuildFilterMiddleware."""

from urllib.parse import parse_qsl

import pytest
from fastapi import FastAPI, HTTPException, Request
from starlette.testclient import TestClient
from utils import AppFactory

from stac_auth_proxy.middleware.Cql2BuildFilterMiddleware import (
    Cql2BuildFilterMiddleware,
)


class TestOptionsRequest:
    """Test middleware behavior with OPTIONS requests."""

    def test_options_request_skips_filter_building(self):
        """Test that OPTIONS requests skip CQL2 filter building."""
        app = FastAPI()

        # Create a simple filter that would be applied to items
        async def items_filter(context):
            return "private = false"

        # Add middleware with a filter
        app.add_middleware(
            Cql2BuildFilterMiddleware,
            items_filter=items_filter,
        )

        @app.options("/search")
        async def search_options(request: Request):
            # Check if the filter was built and added to request state
            cql2_filter = getattr(request.state, "cql2_filter", None)
            return {
                "filter_was_built": cql2_filter is not None,
                "methods": ["GET", "POST", "OPTIONS"],
            }

        @app.get("/search")
        async def search_get(request: Request):
            # Check if the filter was built for comparison
            cql2_filter = getattr(request.state, "cql2_filter", None)
            return {
                "filter_was_built": cql2_filter is not None,
            }

        client = TestClient(app)

        # Test OPTIONS request - filter should NOT be built
        options_response = client.options("/search")
        assert options_response.status_code == 200
        options_data = options_response.json()
        assert options_data["filter_was_built"] is False

        # Test GET request - filter SHOULD be built
        get_response = client.get("/search")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["filter_was_built"] is True

    def test_options_request_on_items_endpoint(self):
        """Test that OPTIONS requests skip filter building on items endpoint."""
        app = FastAPI()

        async def items_filter(context):
            return "collection = 'test'"

        app.add_middleware(
            Cql2BuildFilterMiddleware,
            items_filter=items_filter,
        )

        @app.options("/collections/test-collection/items")
        async def items_options(request: Request):
            cql2_filter = getattr(request.state, "cql2_filter", None)
            return {"filter_was_built": cql2_filter is not None}

        @app.get("/collections/test-collection/items")
        async def items_get(request: Request):
            cql2_filter = getattr(request.state, "cql2_filter", None)
            return {"filter_was_built": cql2_filter is not None}

        client = TestClient(app)

        # Test OPTIONS request on items endpoint
        options_response = client.options("/collections/test-collection/items")
        assert options_response.status_code == 200
        assert options_response.json()["filter_was_built"] is False

        # Test GET request on items endpoint for comparison
        get_response = client.get("/collections/test-collection/items")
        assert get_response.status_code == 200
        assert get_response.json()["filter_was_built"] is True


class TestErrorHandling:
    """Test middleware behavior when filter_fcn returns an exception."""

    def test_exception_handling(self):
        """Test that the middleware correctly handles exceptions raised by the filter function."""
        app = FastAPI()

        # Create a simple filter, function raise an exception if user is not "good"
        async def items_filter(context):
            query_params = context["req"].get("query_params", {})
            if query_params.get("user") != "good":
                raise HTTPException(status_code=403, detail="Bad user")

            return "private = false"

        # Add middleware with a filter
        app.add_middleware(
            Cql2BuildFilterMiddleware,
            items_filter=items_filter,
        )

        @app.get("/search")
        async def search_get(request: Request):
            return {}

        client = TestClient(app)

        # Test GET request SHOULD return 403 for bad user
        get_response = client.get("/search")
        assert get_response.status_code == 403

        # Test GET request SHOULD return 200 for good user
        get_response = client.get("/search", params={"user": "good"})
        assert get_response.status_code == 200

    def test_exception_headers_are_kept(self):
        """Headers set on the HTTPException, such as WWW-Authenticate, reach the client."""
        app = FastAPI()

        async def items_filter(context):
            raise HTTPException(
                status_code=401,
                detail="Not authenticated",
                headers={"WWW-Authenticate": 'Bearer realm="stac"'},
            )

        app.add_middleware(
            Cql2BuildFilterMiddleware,
            items_filter=items_filter,
        )

        @app.get("/search")
        async def search_get(request: Request):
            return {}

        response = TestClient(app).get("/search")
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == 'Bearer realm="stac"'


class TestQueryParamConsistency:
    """Filter factories must see the same query params the upstream acts on."""

    # A policy keyed on a query param, as the docs suggest ("tailor the filter").
    app_factory = AppFactory(
        oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
        default_public=True,
        items_filter={
            "cls": "stac_auth_proxy.filters:Template",
            "args": [
                "{{ 'true' if req.query_params.get('collections') == 'public' "
                "else \"collection = 'public'\" }}"
            ],
        },
    )

    def test_raw_non_ascii_seen_as_forwarded(self, mock_upstream, source_api_server):
        """Raw UTF-8 query bytes reach the factory decoded as the upstream decodes them."""
        app = AppFactory(
            oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
            default_public=True,
            items_filter={
                "cls": "stac_auth_proxy.filters:Template",
                "args": ["collection = '{{ req.query_params.get('collections') }}'"],
            },
        )(upstream_url=source_api_server)

        async def raw_query_app(scope, receive, send):
            if scope["type"] == "http":
                scope = {**scope, "query_string": "collections=café".encode()}
            await app(scope, receive, send)

        assert TestClient(raw_query_app).get("/search").status_code == 200
        [request] = mock_upstream.call_args[0]
        assert request.url.params["collections"] == "café"
        assert request.url.params["filter"] == "(collection = 'café')"

    @pytest.mark.parametrize(
        "query_string",
        [
            b"collections=secret&collections=public",
            b"collections=public&collections=secret",
        ],
    )
    def test_duplicate_query_params_rejected(
        self, mock_upstream, source_api_server, query_string
    ):
        """Duplicate keys would let the factory and the upstream disagree; reject them."""
        app = self.app_factory(upstream_url=source_api_server)

        async def raw_query_app(scope, receive, send):
            if scope["type"] == "http":
                scope = {**scope, "query_string": query_string}
            await app(scope, receive, send)

        response = TestClient(raw_query_app).get("/search")
        assert response.status_code == 400
        assert response.json() == {
            "code": "BadRequest",
            "description": "Repeated query parameters are not supported: "
            "collections. Use comma-separated values instead (e.g. collections=a,b).",
        }
        mock_upstream.assert_not_called()

    @pytest.mark.parametrize(
        "query_string",
        [
            # Express's qs parser (stac-server) reads "collections[]" as "collections"
            b"collections[]=secret",
            b"collections=public&collections[]=secret",
            b"collections%5B%5D=secret",
        ],
    )
    def test_bracketed_query_params_rejected(
        self, mock_upstream, source_api_server, query_string
    ):
        """Bracket params would reach the factory under a different key than upstream."""
        app = self.app_factory(upstream_url=source_api_server)

        async def raw_query_app(scope, receive, send):
            if scope["type"] == "http":
                scope = {**scope, "query_string": query_string}
            await app(scope, receive, send)

        response = TestClient(raw_query_app).get("/search")
        assert response.status_code == 400
        assert response.json()["description"].startswith(
            "Bracketed query parameters are not supported: collections[]."
        )
        mock_upstream.assert_not_called()

    @pytest.mark.parametrize(
        "collections, expected_filter",
        [("public", "true"), ("secret", "(collection = 'public')")],
    )
    def test_unique_query_params_allowed(
        self, mock_upstream, source_api_server, collections, expected_filter
    ):
        """Requests without duplicate keys are filtered on the value the upstream gets."""
        client = TestClient(self.app_factory(upstream_url=source_api_server))
        response = client.get("/search", params={"collections": collections})
        assert response.status_code == 200
        [request] = mock_upstream.call_args[0]
        assert parse_qsl(request.url.query.decode()) == [
            ("filter", expected_filter),
            ("filter-lang", "cql2-text"),
            ("collections", collections),
        ]

    def test_duplicate_query_params_allowed_without_filter(
        self, mock_upstream, source_api_server
    ):
        """Endpoints with no filter configured are unaffected."""
        client = TestClient(self.app_factory(upstream_url=source_api_server))
        response = client.get("/collections?a=1&a=2")
        assert response.status_code == 200
        [request] = mock_upstream.call_args[0]
        assert request.url.query == b"a=1&a=2"
