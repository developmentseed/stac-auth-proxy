"""Utility functions."""

import json
import logging
import re
from collections import Counter
from typing import Iterable, Optional
from urllib.parse import quote, quote_from_bytes, urlencode

from cql2 import Expr
from starlette.datastructures import QueryParams

logger = logging.getLogger(__name__)

# Reserved characters with no special meaning inside a query value, left unescaped
# to keep geometry-heavy filters compact. Everything that delimits or decodes
# (& = # + % ; space) is still escaped.
_QS_SAFE = "!$'()*,/:?@[]"

_ASCII_PRINTABLE = "".join(map(chr, range(0x21, 0x7F)))

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


# Express's qs and Node's querystring read only the first 1000 "&"-separated pieces
# (empty ones included), so a padded query could hide params from the upstream that
# filter factories see. STAC queries need far fewer.
MAX_QUERY_PIECES = 100


def check_query_size(qs: bytes) -> None:
    """Reject query strings with more pieces than an upstream is sure to read."""
    if qs and qs.count(b"&") + 1 > MAX_QUERY_PIECES:
        raise InvalidFilterRequestError(
            f"Too many query parameters (at most {MAX_QUERY_PIECES})."
        )


def check_unique_params(keys: Iterable[str]) -> None:
    """
    Reject query params that filter factories and the upstream could read
    differently: repeated params, as upstreams disagree on which value wins (first,
    last, or all as an array) while factories see one, and bracket params
    ("collections[]"), which Express's qs parser reads as "collections".
    """
    keys = list(keys)
    bracketed = sorted({key for key in keys if "[" in key})
    if bracketed:
        raise InvalidFilterRequestError(
            f"Bracketed query parameters are not supported: {', '.join(bracketed)}. "
            "Use comma-separated values instead (e.g. collections=a,b)."
        )
    repeated = sorted(key for key, n in Counter(keys).items() if n > 1)
    if repeated:
        raise InvalidFilterRequestError(
            f"Repeated query parameters are not supported: {', '.join(repeated)}. "
            "Use comma-separated values instead (e.g. collections=a,b)."
        )


def parse_query_params(qs: bytes) -> QueryParams:
    """
    Parse a raw query string (``scope["query_string"]``).

    Starlette's ``request.query_params`` decodes raw non-ASCII bytes as latin-1,
    unlike their percent-encoded form (UTF-8). Percent-encode them first so filter
    factories and the upstream see the same value.
    """
    return QueryParams(quote_from_bytes(qs, safe=_ASCII_PRINTABLE))


def append_qs_filter(qs: bytes, filter: Expr) -> bytes:
    """
    Insert a filter expression into a raw query string (``scope["query_string"]``).
    If a filter already exists, combine them.

    The query string is parsed exactly as filter factories receive it
    (``dict(request.query_params)``), so the forwarded params are the ones the
    filter was computed for. Repeated params are rejected rather than collapsed,
    as upstreams disagree on which value wins.
    """
    params = parse_query_params(qs)
    check_unique_params(k for k, _ in params.multi_items())
    qs_dict = dict(params)  # look-alike filter params are checked by append_body_filter
    new_qs_dict = append_body_filter(
        qs_dict, filter, qs_dict.get("filter-lang") or "cql2-text"
    )
    # Filter first: Express's qs and Node's querystring keep only the first 1000
    # params, so a client padding the query can't push the filter past them.
    filter_first = {
        "filter": new_qs_dict.pop("filter"),
        "filter-lang": new_qs_dict.pop("filter-lang"),
        **new_qs_dict,
    }
    return dict_to_query_string(filter_first).encode("utf-8")


def append_body_filter(
    body: dict, filter: Expr, filter_lang: Optional[str] = None
) -> dict:
    """Insert a filter expression into a request body. If a filter already exists, combine them."""
    _check_filter_params(body)
    cur_filter = body.get("filter")
    filter_lang = filter_lang or body.get("filter-lang") or "cql2-json"
    if cur_filter not in (None, "", {}, []):
        try:
            client_filter = Expr(cur_filter)
        except Exception as e:  # cql2 raises a bare Exception for invalid input
            raise InvalidFilterRequestError(f"Invalid filter: {e}") from e
        filter = filter + client_filter
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
