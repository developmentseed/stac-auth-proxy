"""Tests for Jinja2 CQL2 filter (simplified for readability)."""

import json

import cql2
import pytest
from fastapi.testclient import TestClient
from utils import AppFactory, get_upstream_request

FILTER_EXPR_CASES = [
    pytest.param(
        "(properties.private = false)",
        "(properties.private = false)",
        "(properties.private = false)",
        id="simple_not_templated",
    ),
    pytest.param(
        "{{ '(properties.private = false)' if payload is none else true }}",
        "true",
        "(properties.private = false)",
        id="simple_templated",
    ),
    pytest.param(
        "(private = true)",
        "(private = true)",
        "(private = true)",
        id="complex_not_templated",
    ),
    pytest.param(
        """{{ '{"op": "=", "args": [{"property": "private"}, true]}' if payload is none else true }}""",
        "true",
        """{"op": "=", "args": [{"property": "private"}, true]}""",
        id="complex_templated",
    ),
]

SEARCH_POST_QUERIES = [
    pytest.param(
        {
            "collections": ["example-collection"],
            "bbox": [-120.5, 35.7, -120.0, 36.0],
            "datetime": "2021-06-01T00:00:00Z/2021-06-30T23:59:59Z",
        },
        id="no_filter",
    ),
    pytest.param(
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
        id="with_filter",
    ),
]

SEARCH_GET_QUERIES = [
    pytest.param(
        {
            "collections": "example-collection",
            "bbox": "160.6,-55.95,-170,-25.89",
            "datetime": "2021-06-01T00:00:00Z/2021-06-30T23:59:59Z",
        },
        id="no_filter",
    ),
    pytest.param(
        {
            "bbox": "160.6,-55.95,-170,-25.89",
            "filter-lang": "cql2-text",
            "filter": "((collection = 'landsat-8-l1') AND (\"eo:cloud_cover\" <= 20) AND (platform = 'landsat-8'))",
            "limit": "5",
        },
        id="with_filter_text",
    ),
    pytest.param(
        {
            "bbox": "160.6,-55.95,-170,-25.89",
            "filter-lang": "cql2-json",
            "filter": json.dumps(
                {
                    "op": "and",
                    "args": [
                        {
                            "op": "=",
                            "args": [{"property": "collection"}, "landsat-8-l1"],
                        },
                        {"op": "<=", "args": [{"property": "eo:cloud_cover"}, 20]},
                        {"op": "=", "args": [{"property": "platform"}, "landsat-8"]},
                    ],
                }
            ),
            "limit": "5",
        },
        id="with_filter_json",
    ),
]

ITEMS_LIST_QUERIES = [
    pytest.param(
        {},
        id="items_no_filter",
    ),
    pytest.param(
        {
            "filter-lang": "cql2-text",
            "filter": "((collection = 'landsat-8-l1') AND (\"eo:cloud_cover\" <= 20) AND (platform = 'landsat-8'))",
        },
        id="items_with_filter",
    ),
]

app_factory = AppFactory(
    oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
    default_public=False,
)


def _build_items_filter_client(
    *,
    src_api_server: str,
    template_expr: str,
    is_authenticated: bool,
    token_builder,
):
    """Build a TestClient configured for either authenticated or anonymous usage."""
    app = app_factory(
        upstream_url=src_api_server,
        items_filter={
            "cls": "stac_auth_proxy.filters:Template",
            "args": [template_expr.strip()],
        },
        default_public=True,
    )
    headers = (
        {"Authorization": f"Bearer {token_builder({'sub': 'test-user'})}"}
        if is_authenticated
        else {}
    )
    return TestClient(app, headers=headers)


@pytest.mark.parametrize(
    "filter_template_expr, expected_auth_filter, expected_anon_filter",
    FILTER_EXPR_CASES,
)
@pytest.mark.parametrize("is_authenticated", [True, False], ids=["auth", "anon"])
@pytest.mark.parametrize("input_query", SEARCH_POST_QUERIES)
async def test_search_post(
    mock_upstream,
    source_api_server,
    filter_template_expr,
    expected_auth_filter,
    expected_anon_filter,
    is_authenticated,
    input_query,
    token_builder,
):
    """Test that POST /search merges the upstream query with the templated filter."""
    response = _build_items_filter_client(
        src_api_server=source_api_server,
        template_expr=filter_template_expr,
        is_authenticated=is_authenticated,
        token_builder=token_builder,
    ).post("/search", json=input_query)
    response.raise_for_status()

    # Retrieve the JSON body that was actually sent upstream
    proxied_request = await get_upstream_request(mock_upstream)
    proxied_body = json.loads(proxied_request.body)

    # Determine the expected combined filter
    proxy_filter = cql2.Expr(
        expected_auth_filter if is_authenticated else expected_anon_filter
    )
    input_filter = input_query.get("filter")
    if input_filter:
        proxy_filter += cql2.Expr(input_filter)

    expected_output = {
        **input_query,
        "filter": proxy_filter.to_json(),
        "filter-lang": "cql2-json",
    }

    assert (
        proxied_body == expected_output
    ), "POST query should combine filter expressions."


@pytest.mark.parametrize(
    "filter_template_expr, expected_auth_filter, expected_anon_filter",
    FILTER_EXPR_CASES,
)
@pytest.mark.parametrize("is_authenticated", [True, False], ids=["auth", "anon"])
@pytest.mark.parametrize("input_query", SEARCH_GET_QUERIES)
async def test_search_get(
    mock_upstream,
    source_api_server,
    filter_template_expr,
    expected_auth_filter,
    expected_anon_filter,
    is_authenticated,
    input_query,
    token_builder,
):
    """Test that GET /search merges the upstream query params with the templated filter."""
    client = _build_items_filter_client(
        src_api_server=source_api_server,
        template_expr=filter_template_expr,
        is_authenticated=is_authenticated,
        token_builder=token_builder,
    )
    response = client.get("/search", params=input_query)
    response.raise_for_status()

    # For GET, we expect the upstream body to be empty, but URL params to be appended
    proxied_request = await get_upstream_request(mock_upstream)
    assert proxied_request.body == ""

    # Determine the expected combined filter
    proxy_filter = cql2.Expr(
        expected_auth_filter if is_authenticated else expected_anon_filter
    )
    input_filter = input_query.get("filter")
    if input_filter:
        proxy_filter += cql2.Expr(input_filter)

    filter_lang = input_query.get("filter-lang", "cql2-text")
    expected_output = {
        **input_query,
        "filter": (
            proxy_filter.to_text()
            if filter_lang == "cql2-text"
            else proxy_filter.to_json()
        ),
        "filter-lang": filter_lang,
    }
    assert (
        proxied_request.query_params == expected_output
    ), "GET query should combine filter expressions."


@pytest.mark.parametrize(
    "filter_template_expr, expected_auth_filter, expected_anon_filter",
    FILTER_EXPR_CASES,
)
@pytest.mark.parametrize("is_authenticated", [True, False], ids=["auth", "anon"])
@pytest.mark.parametrize("input_query", ITEMS_LIST_QUERIES)
async def test_items_list(
    mock_upstream,
    source_api_server,
    filter_template_expr,
    expected_auth_filter,
    expected_anon_filter,
    is_authenticated,
    input_query,
    token_builder,
):
    """Test that GET /collections/foo/items merges query params with the templated filter."""
    client = _build_items_filter_client(
        src_api_server=source_api_server,
        template_expr=filter_template_expr,
        is_authenticated=is_authenticated,
        token_builder=token_builder,
    )
    response = client.get("/collections/foo/items", params=input_query)
    response.raise_for_status()

    # For GET items, we also expect an empty body and appended querystring
    proxied_request = await get_upstream_request(mock_upstream)
    assert proxied_request.body == ""

    # Only the appended filter (no input_filter merges in these particular tests),
    # but you could do similar merging logic if needed.
    proxy_filter = cql2.Expr(
        expected_auth_filter if is_authenticated else expected_anon_filter
    )
    assert proxied_request.query_params == {
        "filter-lang": "cql2-text",
        "filter": (
            proxy_filter + cql2.Expr(qs_filter)
            if (qs_filter := input_query.get("filter"))
            else proxy_filter
        ).to_text(),
    }, "Items query should include only the appended filter expression."


@pytest.mark.parametrize("is_authenticated", [True, False], ids=["auth", "anon"])
def test_item_get(
    source_api_server, is_authenticated, token_builder, source_api_responses
):
    """Test that GET /collections/foo/items/bar is rejected."""
    client = _build_items_filter_client(
        src_api_server=source_api_server,
        template_expr="{{ '(properties.private = false)' if payload is none else true }}",
        is_authenticated=is_authenticated,
        token_builder=token_builder,
    )
    source_api_responses["/collections/{collection_id}/items/{item_id}"]["GET"] = {
        "id": "bar",
        "properties": {"private": True},
    }
    response = client.get("/collections/foo/items/bar")
    if is_authenticated:
        assert response.status_code == 200
        assert response.json()["id"] == "bar"
        assert response.json()["properties"].get("private") is True
    else:
        assert response.status_code == 404
        assert response.json() == {
            "code": "NotFoundError",
            "description": "Record not found.",
        }


@pytest.mark.parametrize("is_authenticated", [True, False], ids=["auth", "anon"])
async def test_search_post_empty_body(
    source_api_server,
    is_authenticated,
    token_builder,
):
    """Test that POST /search with empty body."""
    client = _build_items_filter_client(
        src_api_server=source_api_server,
        template_expr="(properties.private = false)",
        is_authenticated=is_authenticated,
        token_builder=token_builder,
    )

    # Send request with Content-Length header that doesn't match actual body size
    response = client.post(
        "/search",
        json={},
    )

    assert response.status_code == 200


COLLECTIONS_FILTER_CASES = [
    pytest.param(
        "(properties.private = false)",
        "(properties.private = false)",
        "(properties.private = false)",
        id="simple_collections_filter",
    ),
    pytest.param(
        "{{ '(properties.private = false)' if payload is none else true }}",
        "true",
        "(properties.private = false)",
        id="templated_collections_filter",
    ),
]

COLLECTIONS_QUERIES = [
    pytest.param(
        {},
        id="collections_no_filter",
    ),
    pytest.param(
        {
            "filter-lang": "cql2-text",
            "filter": "(properties.private = true)",
        },
        id="collections_with_filter",
    ),
]


def _build_collections_filter_client(
    *,
    src_api_server: str,
    template_expr: str,
    is_authenticated: bool,
    token_builder,
):
    """Build a TestClient configured for either authenticated or anonymous usage."""
    app = app_factory(
        upstream_url=src_api_server,
        collections_filter={
            "cls": "stac_auth_proxy.filters:Template",
            "args": [template_expr.strip()],
        },
        default_public=True,
    )
    headers = (
        {"Authorization": f"Bearer {token_builder({'sub': 'test-user'})}"}
        if is_authenticated
        else {}
    )
    return TestClient(app, headers=headers)


@pytest.mark.parametrize(
    "filter_template_expr, expected_auth_filter, expected_anon_filter",
    COLLECTIONS_FILTER_CASES,
)
@pytest.mark.parametrize("is_authenticated", [True, False], ids=["auth", "anon"])
@pytest.mark.parametrize("input_query", COLLECTIONS_QUERIES)
async def test_collections_list(
    mock_upstream,
    source_api_server,
    filter_template_expr,
    expected_auth_filter,
    expected_anon_filter,
    is_authenticated,
    input_query,
    token_builder,
):
    """Test that GET /collections merges query params with the templated filter."""
    client = _build_collections_filter_client(
        src_api_server=source_api_server,
        template_expr=filter_template_expr,
        is_authenticated=is_authenticated,
        token_builder=token_builder,
    )
    response = client.get("/collections", params=input_query)
    response.raise_for_status()

    # For GET collections, we expect an empty body and appended querystring
    proxied_request = await get_upstream_request(mock_upstream)
    assert proxied_request.body == ""

    # Determine the expected combined filter
    proxy_filter = cql2.Expr(
        expected_auth_filter if is_authenticated else expected_anon_filter
    )
    input_filter = input_query.get("filter")
    if input_filter:
        proxy_filter += cql2.Expr(input_filter)

    filter_lang = input_query.get("filter-lang", "cql2-text")
    expected_output = {
        **input_query,
        "filter": (
            proxy_filter.to_text()
            if filter_lang == "cql2-text"
            else proxy_filter.to_json()
        ),
        "filter-lang": filter_lang,
    }
    assert (
        proxied_request.query_params == expected_output
    ), "Collections query should combine filter expressions."


@pytest.mark.parametrize(
    "filter_template_expr, expected_auth_filter, expected_anon_filter",
    COLLECTIONS_FILTER_CASES,
)
@pytest.mark.parametrize("is_authenticated", [True, False], ids=["auth", "anon"])
async def test_collection_get(
    source_api_server,
    filter_template_expr,
    expected_auth_filter,
    expected_anon_filter,
    is_authenticated,
    token_builder,
    source_api_responses,
):
    """Test that GET /collections/{collection_id} applies the templated filter."""
    client = _build_collections_filter_client(
        src_api_server=source_api_server,
        template_expr=filter_template_expr,
        is_authenticated=is_authenticated,
        token_builder=token_builder,
    )
    response_body = {
        "id": "foo",
        "properties": {"private": True},
    }
    source_api_responses["/collections/{collection_id}"]["GET"] = response_body
    response = client.get("/collections/foo")

    expected_applied_filter = cql2.Expr(
        expected_auth_filter if is_authenticated else expected_anon_filter
    )
    expected_response_status = (
        200 if expected_applied_filter.matches(response_body) else 404
    )
    assert response.status_code == expected_response_status
