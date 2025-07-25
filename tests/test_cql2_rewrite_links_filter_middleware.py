from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request, Response
from starlette.testclient import TestClient

from stac_auth_proxy.middleware.Cql2RewriteLinksFilterMiddleware import (
    Cql2RewriteLinksFilterMiddleware,
)


@pytest.fixture
def app_with_middleware():
    app = FastAPI()
    app.add_middleware(Cql2RewriteLinksFilterMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request):
        # Simulate a response with links containing a filter in the query and body
        return {
            "links": [
                {
                    "rel": "self",
                    "href": "http://example.com/search?filter=foo&filter-lang=cql2-text",
                },
                {
                    "rel": "post",
                    "body": {"filter": "foo", "filter-lang": "cql2-json"},
                },
            ]
        }

    return app


def test_rewrite_links_with_filter(app_with_middleware):
    # Patch cql2.Expr to simulate to_text and to_json
    with patch(
        "stac_auth_proxy.middleware.Cql2RewriteLinksFilterMiddleware.Expr"
    ) as MockExpr:
        mock_expr = MagicMock()
        mock_expr.to_text.return_value = "bar"
        mock_expr.to_json.return_value = {"foo": "bar"}
        MockExpr.return_value = mock_expr

        client = TestClient(app_with_middleware)
        response = client.get("/test?filter=foo")
        assert response.status_code == 200
        data = response.json()
        # The filter in the href should be rewritten
        assert any(
            "filter=bar" in link["href"] for link in data["links"] if "href" in link
        )
        # The filter in the body should be rewritten
        assert any(
            link.get("body", {}).get("filter") == {"foo": "bar"}
            for link in data["links"]
        )


def test_remove_filter_from_links(app_with_middleware):
    # Patch cql2.Expr to return None (no filter)
    with patch(
        "stac_auth_proxy.middleware.Cql2RewriteLinksFilterMiddleware.Expr"
    ) as MockExpr:
        MockExpr.return_value = None
        client = TestClient(app_with_middleware)
        response = client.get("/test")
        assert response.status_code == 200
        data = response.json()
        # The filter should be removed from href and body
        for link in data["links"]:
            if "href" in link:
                assert "filter=" not in link["href"]
            if "body" in link:
                assert "filter" not in link["body"]
                assert "filter-lang" not in link["body"]


def test_passthrough_when_no_filter_state(app_with_middleware):
    # Simulate no filter in request.state
    with patch(
        "stac_auth_proxy.middleware.Cql2RewriteLinksFilterMiddleware.Expr"
    ) as MockExpr:
        MockExpr.return_value = None
        client = TestClient(app_with_middleware)
        response = client.get("/test")
        assert response.status_code == 200
        data = response.json()
        # Should be unchanged (filter removed)
        for link in data["links"]:
            if "href" in link:
                assert "filter=" not in link["href"]
            if "body" in link:
                assert "filter" not in link["body"]
                assert "filter-lang" not in link["body"]


def test_non_json_response(app_with_middleware):
    # Add a route that returns plain text
    app = app_with_middleware

    @app.get("/plain")
    async def plain():
        return Response(content="not json", media_type="text/plain")

    client = TestClient(app)
    response = client.get("/plain")
    assert response.status_code == 200
    assert response.text == "not json"
