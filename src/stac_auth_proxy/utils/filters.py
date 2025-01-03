"""Utility functions."""

import re
from urllib.parse import parse_qs, urlencode

from cql2 import Expr


def insert_filter(qs: str, filter: Expr) -> str:
    """Insert a filter expression into a query string. If a filter already exists, combine them."""
    qs_dict = parse_qs(qs)

    filters = [Expr(f) for f in qs_dict.get("filter", [])]
    filters.append(filter)

    combined_filter = Expr(" AND ".join(e.to_text() for e in filters))
    combined_filter.validate()

    qs_dict["filter"] = [combined_filter.to_text()]

    return urlencode(qs_dict, doseq=True)


def is_collection_endpoint(path: str) -> bool:
    """Check if the path is a collection endpoint."""
    # TODO: Expand this to cover all cases where a collection filter should be applied
    return path == "/collections"


def is_item_endpoint(path: str) -> bool:
    """Check if the path is an item endpoint."""
    # TODO: Expand this to cover all cases where an item filter should be applied
    return bool(re.compile(r"^/collections/([^/]+)/items$").match(path))
