"""Utility functions."""

import re
from urllib.parse import parse_qs, urlencode

from cql2 import Expr


def append_qs_filter(qs: str, filter: Expr) -> str:
    """Insert a filter expression into a query string. If a filter already exists, combine them."""
    qs_dict = parse_qs(qs)

    for qs_filter in qs_dict.get("filter", []):
        filter += Expr(qs_filter)

    qs_dict["filter"] = filter.to_text()
    qs_dict["filter-lang"] = "cql2-text"

    return urlencode(qs_dict, doseq=True)


def append_body_filter(body: dict, filter: Expr) -> dict:
    """Insert a filter expression into a request body. If a filter already exists, combine them."""
    cur_filter = body.get("filter")
    if cur_filter:
        filter = filter + Expr(cur_filter)
    body["filter"] = filter.to_json()
    body["filter-lang"] = "cql2-json"
    return body


def is_collection_endpoint(path: str) -> bool:
    """Check if the path is a collection endpoint."""
    # TODO: Expand this to cover all cases where a collection filter should be applied
    return path == "/collections"


def is_item_endpoint(path: str) -> bool:
    """Check if the path is an item endpoint."""
    # TODO: Expand this to cover all cases where an item filter should be applied
    return bool(re.compile(r"^(/collections/([^/]+)/items$|/search)").match(path))


def is_search_endpoint(path: str) -> bool:
    """Check if the path is a search endpoint."""
    return path == "/search"
