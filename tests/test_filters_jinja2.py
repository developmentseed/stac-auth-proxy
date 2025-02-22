"""Tests for Jinja2 CQL2 filter."""

import json
from typing import cast

import cql2
import pytest
from fastapi.testclient import TestClient
from httpx import Request
from utils import AppFactory

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
    default_public=False,
)


# def test_collections_filter_contained_by_token(
#     mock_upstream, source_api_server, token_builder
# ):
#     """Test that the collections filter is applied correctly."""
#     app = app_factory(
#         upstream_url=source_api_server,
#         collections_filter={
#             "cls": "stac_auth_proxy.filters.Template",
#             "args": [
#                 "A_CONTAINEDBY(id, ('{{ token.collections | join(\"', '\") }}' ))"
#             ],
#         },
#     )

#     auth_token = token_builder({"collections": ["foo", "bar"]})
#     client = TestClient(app, headers={"Authorization": f"Bearer {auth_token}"})
#     response = client.get("/collections")

#     assert response.status_code == 200
#     assert mock_upstream.call_count == 1
#     [r] = mock_upstream.call_args[0]
#     assert parse_qs(r.url.query.decode()) == {
#         "filter": ["a_containedby(id, ('foo', 'bar'))"]
#     }


# @pytest.mark.parametrize(
#     "authenticated, expected_filter",
#     [
#         (True, "true"),
#         (False, "(private = false)"),
#     ],
# )
# def test_collections_filter_private_and_public(
#     mock_upstream, source_api_server, token_builder, authenticated, expected_filter
# ):
#     """Test that filter can be used for private/public collections."""
#     app = app_factory(
#         upstream_url=source_api_server,
#         collections_filter={
#             "cls": "stac_auth_proxy.filters.Template",
#             "args": ["{{ '(private = false)' if token is none else true }}"],
#         },
#         default_public=True,
#     )

#     client = TestClient(
#         app,
#         headers=(
#             {"Authorization": f"Bearer {token_builder({})}"} if authenticated else {}
#         ),
#     )
#     response = client.get("/collections")

#     assert response.status_code == 200
#     assert mock_upstream.call_count == 1
#     [r] = mock_upstream.call_args[0]
#     assert parse_qs(r.url.query.decode()) == {"filter": [expected_filter]}


# @pytest.mark.parametrize(
#     "authenticated, expected_filter",
#     [
#         (True, "true"),
#         (False, '("properties.private" = false)'),
#     ],
# )
# def test_items_filter_private_and_public(
#     mock_upstream, source_api_server, token_builder, authenticated, expected_filter
# ):
#     """Test that filter can be used for private/public collections."""
#     app = app_factory(
#         upstream_url=source_api_server,
#         items_filter={
#             "cls": "stac_auth_proxy.filters.Template",
#             "args": ["{{ '(properties.private = false)' if token is none else true }}"],
#         },
#         default_public=True,
#     )

#     client = TestClient(
#         app,
#         headers=(
#             {"Authorization": f"Bearer {token_builder({})}"} if authenticated else {}
#         ),
#     )
#     response = client.get("/collections/foo/items")

#     assert response.status_code == 200
#     assert mock_upstream.call_count == 1
#     [r] = mock_upstream.call_args[0]
#     assert parse_qs(r.url.query.decode()) == {"filter": [expected_filter]}


# @pytest.mark.parametrize(
#     "filter_template_expr, user_search, expected_anon_search, expected_authenticated_search",
#     [
#         (
#             "{{ '(properties.private = false)' if token is none else true }}",
#             {},
#             {"filter": "(properties.private = false)"},
#             {},
#         ),
#         # ({}, {"filter": {"op": "=", "args": [{"property": "private"}, False]}}, {}),
#         # (True, {"op": "=", "args": [{"property": "private"}, True]}),
#     ],
# )
# def test_search_filters(
#     mock_upstream,
#     source_api_server,
#     token_builder,
#     filter_template_expr,
#     user_search,
#     expected_anon_search,
#     expected_authenticated_search,
# ):
#     """Test that filter can be used for private/public collections."""
#     app = app_factory(
#         upstream_url=source_api_server,
#         items_filter={
#             "cls": "stac_auth_proxy.filters.Template",
#             "args": [filter_template_expr],
#         },
#         default_public=True,
#     )

#     for is_authenticated, expected_search in [
#         (True, expected_authenticated_search),
#         (False, expected_anon_search),
#     ]:
#         headers = (
#             {"Authorization": f"Bearer {token_builder({})}"} if is_authenticated else {}
#         )
#         client = TestClient(app, headers=headers)
#         response = client.post("/search", json=user_search)

#         assert response.status_code == 200
#         assert mock_upstream.call_count == 1
#         [r] = cast(list[Request], mock_upstream.call_args[0])
#         body = r.read().decode()
#         print(f"req {json.loads(body)=}")
#         assert json.loads(body) == expected_search
#         mock_upstream.reset_mock()


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
    """Test filter is applied to search with full-featured filtering."""
    # Setup app
    app = app_factory(
        upstream_url=source_api_server,
        items_filter={
            "cls": "stac_auth_proxy.filters.Template",
            "args": [filter_template_expr.strip()],
        },
        default_public=True,
    )

    # Query API
    headers = (
        {"Authorization": f"Bearer {token_builder({})}"} if is_authenticated else {}
    )
    response = TestClient(app, headers=headers).post("/search", json=input_query)
    response.raise_for_status()

    # Retrieve query from upstream
    assert mock_upstream.call_count == 1
    [r] = cast(list[Request], mock_upstream.call_args[0])
    output_query = json.loads(r.read().decode())

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
        output_query == expected_output_query
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
    """Test filter is applied to search with fimple filtering."""
    # Setup app
    app = app_factory(
        upstream_url=source_api_server,
        items_filter={
            "cls": "stac_auth_proxy.filters.Template",
            "args": [filter_template_expr.strip()],
        },
        default_public=True,
    )

    # Query API
    headers = (
        {"Authorization": f"Bearer {token_builder({})}"} if is_authenticated else {}
    )
    response = TestClient(app, headers=headers).get("/search", params=input_query)
    response.raise_for_status()

    # Retrieve query from upstream
    assert mock_upstream.call_count == 1
    [r] = cast(list[Request], mock_upstream.call_args[0])
    assert r.read().decode() == ""
    upstream_querystring = dict(r.url.params)

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
