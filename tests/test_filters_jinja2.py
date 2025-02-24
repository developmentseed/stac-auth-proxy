"""Tests for Jinja2 CQL2 filter."""

import json
from typing import cast
from unittest.mock import MagicMock

import cql2
import pytest
from fastapi.testclient import TestClient
from httpx import Request
from utils import AppFactory

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
    default_public=False,
)


@pytest.mark.parametrize(
    "filter_template_expr, auth_filter, anon_filter",
    [
        # Simple filter, not templated
        [
            "(properties.private = false)",
            "(properties.private = false)",
            "(properties.private = false)",
        ],
        # Simple filter, templated
        [
            "{{ '(properties.private = false)' if token is none else true }}",
            "true",
            "(properties.private = false)",
        ],
        # Complex filter, not templated
        [
            """{
                "op": "=", 
                "args": [{"property": "private"}, true]
            }""",
            """{
                "op": "=", 
                "args": [{"property": "private"}, true]
            }""",
            """{
                "op": "=", 
                "args": [{"property": "private"}, true]
            }""",
        ],
        # Complex filter, templated
        [
            """{{ '{"op": "=", "args": [{"property": "private"}, true]}' if token is none else true }}""",
            "true",
            """{"op": "=", "args": [{"property": "private"}, true]}""",
        ],
    ],
)
@pytest.mark.parametrize("is_authenticated", [True, False])
@pytest.mark.parametrize(
    "input_query",
    [
        # Not using filter
        {
            "collections": ["example-collection"],
            "bbox": [-120.5, 35.7, -120.0, 36.0],
            "datetime": "2021-06-01T00:00:00Z/2021-06-30T23:59:59Z",
        },
        # Using filter
        {
            "filter-lang": "cql2-json",
            "filter": {
                "op": "and",
                "args": [
                    {"op": "=", "args": [{"property": "collection"}, "landsat-8-l1"]},
                    {"op": "<=", "args": [{"property": "eo:cloud_cover"}, 20]},
                    {"op": "=", "args": [{"property": "platform"}, "landsat-8"]},
                ],
            },
            "limit": 5,
        },
    ],
)
def test_search_post(
    mock_upstream,
    source_api_server,
    filter_template_expr,
    auth_filter,
    anon_filter,
    is_authenticated,
    input_query,
    token_builder,
):
    """Append body with generated CQL2 query."""
    response = _build_client(
        src_api_server=source_api_server,
        template_expr=filter_template_expr,
        is_authenticated=is_authenticated,
        token_builder=token_builder,
    ).post("/search", json=input_query)
    response.raise_for_status()

    # Retrieve query from upstream
    upstream_body = json.loads(_get_upstream_request(mock_upstream)[0])

    # Parse query from upstream
    input_filter = input_query.get("filter")
    expected_filter = auth_filter if is_authenticated else anon_filter
    expected_filter_exprs = [
        cql2.Expr(expr).to_text()
        for expr in [input_filter, expected_filter.strip()]
        if expr
    ]

    expected_output_query = {
        **input_query,
        "filter": cql2.Expr(" AND ".join(expected_filter_exprs)).to_json(),
    }

    assert (
        upstream_body == expected_output_query
    ), "Query should be combined with the filter expression."


@pytest.mark.parametrize(
    "filter_template_expr, auth_filter, anon_filter",
    [
        # Simple filter, not templated
        [
            "(properties.private = false)",
            "(properties.private = false)",
            "(properties.private = false)",
        ],
        # Simple filter, templated
        [
            "{{ '(properties.private = false)' if token is none else true }}",
            "true",
            "(properties.private = false)",
        ],
        # Complex filter, not templated
        [
            """{
                "op": "=",
                "args": [{"property": "private"}, true]
            }""",
            """{
                "op": "=",
                "args": [{"property": "private"}, true]
            }""",
            """{
                "op": "=",
                "args": [{"property": "private"}, true]
            }""",
        ],
        # Complex filter, templated
        [
            """{{ '{"op": "=", "args": [{"property": "private"}, true]}' if token is none else true }}""",
            "true",
            """{"op": "=", "args": [{"property": "private"}, true]}""",
        ],
    ],
)
@pytest.mark.parametrize("is_authenticated", [True, False])
@pytest.mark.parametrize(
    "input_query",
    [
        # Not using filter
        {
            "collections": "example-collection",
            "bbox": "160.6,-55.95,-170,-25.89",
            "datetime": "2021-06-01T00:00:00Z/2021-06-30T23:59:59Z",
        },
        # Using filter
        # {
        #     "filter-lang": "cql2-json",
        #     "filter": {
        #         "op": "and",
        #         "args": [
        #             {"op": "=", "args": [{"property": "collection"}, "landsat-8-l1"]},
        #             {"op": "<=", "args": [{"property": "eo:cloud_cover"}, 20]},
        #             {"op": "=", "args": [{"property": "platform"}, "landsat-8"]},
        #         ],
        #     },
        #     "limit": 5,
        # },
    ],
)
def test_search_get(
    mock_upstream,
    source_api_server,
    filter_template_expr,
    auth_filter,
    anon_filter,
    is_authenticated,
    input_query,
    token_builder,
):
    """Append query params with generated CQL2 query."""
    response = _build_client(
        src_api_server=source_api_server,
        template_expr=filter_template_expr,
        is_authenticated=is_authenticated,
        token_builder=token_builder,
    ).get("/search", params=input_query)
    response.raise_for_status()

    # Retrieve query from upstream
    upstream_body, upstream_querystring = _get_upstream_request(mock_upstream)
    assert upstream_body == ""

    # Parse query from upstream
    input_filter = input_query.get("filter")
    expected_filter = auth_filter if is_authenticated else anon_filter
    expected_filter_exprs = [
        cql2.Expr(expr).to_text()
        for expr in [input_filter, expected_filter.strip()]
        if expr
    ]

    # TODO: Use QS, not dict
    expected_output_query = {
        **input_query,
        "filter": cql2.Expr(" AND ".join(expected_filter_exprs)).to_text(),
    }

    assert (
        upstream_querystring == expected_output_query
    ), "Query should be combined with the filter expression."


@pytest.mark.parametrize(
    "filter_template_expr, auth_filter, anon_filter",
    [
        # Simple filter, not templated
        [
            "(properties.private = false)",
            "(properties.private = false)",
            "(properties.private = false)",
        ],
        # Simple filter, templated
        [
            "{{ '(properties.private = false)' if token is none else true }}",
            "true",
            "(properties.private = false)",
        ],
        # Complex filter, not templated
        [
            """{
                "op": "=",
                "args": [{"property": "private"}, true]
            }""",
            """{
                "op": "=",
                "args": [{"property": "private"}, true]
            }""",
            """{
                "op": "=",
                "args": [{"property": "private"}, true]
            }""",
        ],
        # Complex filter, templated
        [
            """{{ '{"op": "=", "args": [{"property": "private"}, true]}' if token is none else true }}""",
            "true",
            """{"op": "=", "args": [{"property": "private"}, true]}""",
        ],
    ],
)
@pytest.mark.parametrize("is_authenticated", [True, False])
@pytest.mark.parametrize(
    "input_query",
    [
        # Not using filter
        {
            "collections": "example-collection",
            "bbox": "160.6,-55.95,-170,-25.89",
            "datetime": "2021-06-01T00:00:00Z/2021-06-30T23:59:59Z",
        },
        # Using filter
        # {
        #     "filter-lang": "cql2-json",
        #     "filter": {
        #         "op": "and",
        #         "args": [
        #             {"op": "=", "args": [{"property": "collection"}, "landsat-8-l1"]},
        #             {"op": "<=", "args": [{"property": "eo:cloud_cover"}, 20]},
        #             {"op": "=", "args": [{"property": "platform"}, "landsat-8"]},
        #         ],
        #     },
        #     "limit": 5,
        # },
    ],
)
def test_items_list(
    mock_upstream,
    source_api_server,
    filter_template_expr,
    auth_filter,
    anon_filter,
    is_authenticated,
    input_query,
    token_builder,
):
    """Append query params with generated CQL2 query."""
    response = _build_client(
        src_api_server=source_api_server,
        template_expr=filter_template_expr,
        is_authenticated=is_authenticated,
        token_builder=token_builder,
    ).get("/collections/foo/items")
    response.raise_for_status()

    body, query = _get_upstream_request(mock_upstream)

    assert body == ""
    assert query == {
        "filter": cql2.Expr(auth_filter if is_authenticated else anon_filter).to_text()
    }


def _build_client(
    *,
    src_api_server: str,
    template_expr: str,
    is_authenticated: bool,
    token_builder,
):
    # Setup app
    app = app_factory(
        upstream_url=src_api_server,
        items_filter={
            "cls": "stac_auth_proxy.filters.Template",
            "args": [template_expr.strip()],
        },
        default_public=True,
    )

    # Query API
    headers = (
        {"Authorization": f"Bearer {token_builder({})}"} if is_authenticated else {}
    )
    return TestClient(app, headers=headers)


def _get_upstream_request(mock_upstream: MagicMock):
    assert mock_upstream.call_count == 1
    [r] = cast(list[Request], mock_upstream.call_args[0])
    return (r.read().decode(), dict(r.url.params))
