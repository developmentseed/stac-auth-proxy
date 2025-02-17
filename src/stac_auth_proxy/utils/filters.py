"""Utility functions."""

import re
from urllib.parse import parse_qs, urlencode

from cql2 import Expr


def combine_filters(filters: list[Expr]) -> Expr:
    """Combine multiple filters into a single filter."""
    combined_filter = Expr(" AND ".join(e.to_text() for e in filters))
    combined_filter.validate()
    return combined_filter


def insert_filter(qs: str, filter: Expr) -> str:
    """Insert a filter expression into a query string. If a filter already exists, combine them."""
    qs_dict = parse_qs(qs)

    filters = [Expr(f) for f in qs_dict.get("filter", [])]
    filters.append(filter)

    qs_dict["filter"] = [combine_filters(filters).to_text()]

    return urlencode(qs_dict, doseq=True)


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
