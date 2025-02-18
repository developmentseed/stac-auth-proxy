"""Tests for Jinja2 CQL2 filter."""

import json
from typing import cast

import cql2
import pytest
from httpx import Request
from fastapi.testclient import TestClient
from utils import AppFactory

from fixtures.demo_searches import SEARCHES

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
        # Not sure what is demonstrated in this...
        # [
        #     """{
        #         "op": "and",
        #         "args": [
        #             { "op": "=", "args": [{ "property": "id" }, "LC08_L1TP_060247_20180905_20180912_01_T1_L1TP" ] },
        #             { "op": "=", "args": [{ "property": "collection" }, "landsat8_l1tp"] }
        #         ]
        #     }"""
        # ]
        # * 3,
    ],
)
@pytest.mark.parametrize("is_authenticated", [True, False])
@pytest.mark.parametrize("input_query", SEARCHES)
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
    # input_filter_lang = input_query.get("filter-lang")
    input_filter = input_query.get("filter")
    expected_filter = auth_filter if is_authenticated else anon_filter
    expected_filter_exprs = [
        cql2.Expr(expr).to_text()
        for expr in [input_filter, expected_filter.strip()]
        if expr
    ]
    expected_filter_out = cql2.Expr(" AND ".join(expected_filter_exprs)).to_json()

    expected_output_query = {
        **input_query,
        "filter": expected_filter_out,
    }

    assert (
        output_query == expected_output_query
    ), "Query should be combined with the filter expression."

    # Reset test
    mock_upstream.reset_mock()
