"""Utility functions."""

import re
from urllib.parse import urlparse

from cql2 import Expr
from fastapi import Request
from fastapi.dependencies.models import Dependant
from starlette.datastructures import QueryParams
from httpx import Headers


def safe_headers(headers: Headers) -> dict[str, str]:
    """Scrub headers that should not be proxied to the client."""
    excluded_headers = [
        "content-length",
        "content-encoding",
    ]
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in excluded_headers
    }


def extract_variables(url: str) -> dict:
    """
    Extract variables from a URL path. Being that we use a catch-all endpoint for the proxy,
    we can't rely on the path parameters that FastAPI provides.
    """
    path = urlparse(url).path
    # This allows either /items or /bulk_items, with an optional item_id following.
    pattern = r"^/collections/(?P<collection_id>[^/]+)(?:/(?:items|bulk_items)(?:/(?P<item_id>[^/]+))?)?/?$"
    match = re.match(pattern, path)
    return {k: v for k, v in match.groupdict().items() if v} if match else {}


def has_any_security_requirements(dependency: Dependant) -> bool:
    """
    Recursively check if any dependency within the hierarchy has a non-empty
    security_requirements list.
    """
    if dependency.security_requirements:
        return True
    return any(
        has_any_security_requirements(sub_dep) for sub_dep in dependency.dependencies
    )


async def apply_filter(request: Request, filter: Expr) -> Request:
    """Apply a CQL2 filter to a request."""
    req_filter = request.query_params.get("filter") or (
        (await request.json()).get("filter")
        if request.headers.get("content-length")
        else None
    )

    new_filter = Expr(" AND ".join(e.to_text() for e in [req_filter, filter] if e))
    new_filter.validate()

    if request.method == "GET":
        updated_scope = request.scope.copy()
        updated_scope["query_string"] = update_qs(
            request.query_params,
            filter=new_filter.to_text(),
        )
        return Request(
            scope=updated_scope,
            receive=request.receive,
            # send=request._send,
        )

    # TODO: Support POST/PUT/PATCH
    # elif request.method == "POST":
    #     request_body = await request.body()
    #     query = request.url.query
    #     query += "&" if query else "?"
    #     query += f"filter={filter}"
    #     request.url.query = query

    return request


def update_qs(query_params: QueryParams, **updates) -> bytes:
    query_dict = {
        **query_params,
        **updates,
    }
    return "&".join(f"{key}={value}" for key, value in query_dict.items()).encode(
        "utf-8"
    )
