"""Utility functions."""

import json
import logging
import re
from collections import Counter
from typing import Iterable, Optional
from urllib.parse import quote, urlencode

from cql2 import Expr
from starlette.datastructures import QueryParams

logger = logging.getLogger(__name__)

# Reserved characters with no special meaning inside a query value, left unescaped
# to keep geometry-heavy filters compact. Everything that delimits or decodes
# (& = # + % ; space) is still escaped.
_QS_SAFE = "!$'()*,/:?@[]"

_FILTER_PARAMS = {"filter", "filter-lang", "filter-crs"}


class InvalidFilterRequestError(ValueError):
    """The request's params can't be unambiguously combined with the proxy's filter."""


def _check_filter_params(keys: Iterable[str]) -> None:
    """
    Reject params that could change how the upstream reads the proxy's filter.

    - Look-alikes of the filter params (e.g. "FILTER", "filter[op]", "filter_lang")
      that some upstreams would read in place of the proxy's.
    - "filter-crs", which would make the upstream read the proxy's filter (e.g.
      its geometries) in a client-chosen CRS.
    """
    for key in keys:
        canonical = re.split(r"[\[\x00]", key, maxsplit=1)[0]
        canonical = canonical.strip().lower().replace("_", "-")
        if canonical in _FILTER_PARAMS and key != canonical:
            raise InvalidFilterRequestError(f"Unsupported parameter {key!r}.")
        if canonical == "filter-crs":
            raise InvalidFilterRequestError(
                "'filter-crs' is not supported on access-controlled endpoints."
            )


def append_qs_filter(qs: bytes, filter: Expr) -> bytes:
    """
    Insert a filter expression into a raw query string (``scope["query_string"]``).
    If a filter already exists, combine them.

    The query string is parsed exactly as filter factories receive it
    (``dict(request.query_params)``), so the forwarded params are the ones the
    filter was computed for. Repeated params are rejected rather than collapsed,
    as upstreams disagree on which value wins.
    """
    params = QueryParams(qs)
    repeated = [
        k for k, n in Counter(k for k, _ in params.multi_items()).items() if n > 1
    ]
    if repeated:
        raise InvalidFilterRequestError(
            f"Repeated query parameters are not supported: {', '.join(repeated)}."
        )
    qs_dict = dict(params)
    _check_filter_params(qs_dict)
    new_qs_dict = append_body_filter(
        qs_dict, filter, qs_dict.get("filter-lang") or "cql2-text"
    )
    return dict_to_query_string(new_qs_dict).encode("utf-8")


def append_body_filter(
    body: dict, filter: Expr, filter_lang: Optional[str] = None
) -> dict:
    """Insert a filter expression into a request body. If a filter already exists, combine them."""
    _check_filter_params(body)
    cur_filter = body.get("filter")
    filter_lang = filter_lang or body.get("filter-lang") or "cql2-json"
    if cur_filter is not None and cur_filter != "":
        filter = filter + Expr(cur_filter)
    if filter_lang == "cql2-text":
        value = filter.to_text()
    else:
        value = filter.to_json()
        if value is False:
            # A bare `false` is falsy: an upstream checking `if filter:` would drop
            # it and return everything. Send an equivalent non-scalar expression.
            value = {"op": "not", "args": [True]}
    return {**body, "filter": value, "filter-lang": filter_lang}


def dict_to_query_string(params: dict) -> str:
    """
    Convert a dictionary to a percent-encoded query string.

    Keys and values MUST be encoded: an unescaped "&", "=", "#", "+" or "%" in a
    client-supplied value (e.g. a filter) would smuggle extra params upstream.
    Non-string values (e.g. a CQL2-JSON filter) are JSON-encoded.
    """
    return urlencode(
        {
            key: (
                val if isinstance(val, str) else json.dumps(val, separators=(",", ":"))
            )
            for key, val in params.items()
        },
        safe=_QS_SAFE,
        quote_via=quote,
    )
