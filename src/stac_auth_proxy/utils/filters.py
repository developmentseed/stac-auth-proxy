"""Utility functions."""

import json
import logging
from dataclasses import dataclass, field
from time import time
from typing import Any, Optional
from urllib.parse import parse_qs

from cql2 import Expr

logger = logging.getLogger(__name__)


def append_qs_filter(qs: str, filter: Expr, filter_lang: Optional[str] = None) -> bytes:
    """Insert a filter expression into a query string. If a filter already exists, combine them."""
    qs_dict = {k: v[0] for k, v in parse_qs(qs).items()}
    new_qs_dict = append_body_filter(
        qs_dict, filter, filter_lang or qs_dict.get("filter-lang", "cql2-text")
    )
    return dict_to_query_string(new_qs_dict).encode("utf-8")


def append_body_filter(
    body: dict, filter: Expr, filter_lang: Optional[str] = None
) -> dict:
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


@dataclass
class MemoryCache:
    """Cache results of a method call for a given key."""

    key: str
    ttl: float = 5.0
    cache: dict[tuple[Any], tuple[Any, float]] = field(default_factory=dict)

    def get(self, ctx: Any) -> Any:
        """Get a value from the cache."""
        key = self.get_value_by_path(ctx, self.key)
        if key not in self.cache:
            logger.debug(
                "%r not in cache, calling function",
                key if len(str(key)) < 10 else f"{key[:9]}...",
            )
            return None

        result, timestamp = self.cache[key]
        age = time() - timestamp
        if age <= self.ttl:
            logger.debug(
                "%r in cache, returning cached result",
                key if len(str(key)) < 10 else f"{str(key)[:9]}...",
            )
            return result
        logger.debug(
            "%r in cache, but expired.",
            key if len(str(key)) < 10 else f"{key[:9]}...",
        )

    def set(self, ctx: Any, value: Any):
        """Set a value in the cache."""
        key = self.get_value_by_path(ctx, self.key)
        self.cache[key] = (value, time())
        self.prune()

    def prune(self):
        """Prune the cache of expired items."""
        self.cache = {
            k: (v, time_entered)
            for k, (v, time_entered) in self.cache.items()
            if time_entered > (time() - self.ttl)
        }

    @staticmethod
    def get_value_by_path(obj: dict, path: str, default: Any = None) -> Any:
        """
        Get a value from a dictionary using dot notation.

        Args:
            obj: The dictionary to search in
            path: The dot notation path (e.g. "payload.sub")
            default: Default value to return if path doesn't exist

        Returns
        -------
            The value at the specified path or default if path doesn't exist
        """
        try:
            for key in path.split("."):
                if obj is None:
                    return default
                obj = obj.get(key, None)
            return obj
        except (AttributeError, KeyError, TypeError):
            return default
