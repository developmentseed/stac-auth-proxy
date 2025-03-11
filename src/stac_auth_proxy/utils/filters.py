"""Utility functions."""

import json
import re
from typing import Optional
from urllib.parse import parse_qs, urlencode

from cql2 import Expr

from .requests import dict_to_bytes


def append_qs_filter(qs: str, filter: Expr, filter_lang: Optional[str] = None) -> bytes:
    """Insert a filter expression into a query string. If a filter already exists, combine them."""
    qs_dict = {k: v[0] for k, v in parse_qs(qs).items()}
    new_qs_dict = append_body_filter(
        qs_dict, filter, filter_lang or qs_dict.get("filter-lang", "cql2-text")
    )
    return dict_to_bytes(
        urlencode(
            {
                k: json.dumps(v) if isinstance(v, (list, dict)) else v
                for k, v in new_qs_dict.items()
            }
        )
    )


def append_body_filter(body: dict, filter: Expr, filter_lang: Optional[str]) -> dict:
    """Insert a filter expression into a request body. If a filter already exists, combine them."""
    cur_filter = body.get("filter")
    filter_lang = filter_lang or body.get("filter-lang", "cql2-json")
    if cur_filter:
        filter = filter + Expr(cur_filter)
    return {
        **body,
        "filter": filter.to_text() if filter_lang == "cql2-text" else filter.to_json(),
        "filter-lang": filter_lang,
    }


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
