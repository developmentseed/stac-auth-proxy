"""Utility functions."""

import json
from typing import Optional
from urllib.parse import parse_qs

from cql2 import Expr


def append_qs_filter(
    qs: str, cql2_filter: Expr, filter_lang: Optional[str] = None
) -> bytes:
    """Insert a filter expression into a query string. If a filter already exists, combine them."""
    qs_dict = {k: v[0] for k, v in parse_qs(qs).items()}
    new_qs_dict = append_body_filter(
        qs_dict, cql2_filter, filter_lang or qs_dict.get("filter-lang", "cql2-text")
    )
    return dict_to_query_string(new_qs_dict).encode("utf-8")


def append_body_filter(
    body: dict, cql2_filter: Expr, filter_lang: Optional[str] = None
) -> dict:
    """Insert a filter expression into a request body. If a filter already exists, combine them."""
    cur_filter = body.get("filter")
    filter_lang = filter_lang or body.get("filter-lang", "cql2-json")
    if cur_filter:
        cql2_filter = cql2_filter + Expr(cur_filter)
    cql2_filter = cql2_filter.reduce()
    return {
        **body,
        "filter": (
            cql2_filter.to_text()
            if filter_lang == "cql2-text"
            else cql2_filter.to_json()
        ),
        "filter-lang": filter_lang,
    }


def dict_to_query_string(params: dict) -> str:
    """
    Convert a dictionary to a query string. Dict values are converted to JSON strings,
    unlike the default behavior of urllib.parse.urlencode.
    """
    parts = []
    for key, val in params.items():
        if isinstance(val, (dict, list)):
            val = json.dumps(val, separators=(",", ":"))
        parts.append(f"{key}={val}")
    return "&".join(parts)
