"""Cache utilities."""

from dataclasses import dataclass, field
from time import time
from typing import Any

from stac_auth_proxy.utils.filters import logger


@dataclass
class MemoryCache:
    """Cache results of a method call for a given key."""

    ttl: float = 5.0
    cache: dict[tuple[Any], tuple[Any, float]] = field(default_factory=dict)
    _last_pruned: float = field(default_factory=time)

    def __getitem__(self, key: Any) -> Any:
        """Get a value from the cache if it is not expired."""
        if key not in self.cache:
            msg = f"{self._key_str(key)!r} not in cache."
            logger.debug(msg)
            raise KeyError(msg)

        result, timestamp = self.cache[key]
        if (time() - timestamp) > self.ttl:
            msg = f"{self._key_str(key)!r} in cache, but expired."
            del self.cache[key]
            logger.debug(msg)
            raise KeyError(f"{key} expired")

        logger.debug(f"{self._key_str(key)} in cache, returning cached result.")
        return result

    def __setitem__(self, key: Any, value: Any):
        """Set a value in the cache."""
        self.cache[key] = (value, time())
        self._prune()

    def __contains__(self, key: Any) -> bool:
        """Check if a key is in the cache and is not expired."""
        try:
            self[key]
            return True
        except KeyError:
            return False

    def get(self, key: Any) -> Any:
        """Get a value from the cache."""
        try:
            return self[key]
        except KeyError:
            return None

    def _prune(self):
        """Prune the cache of expired items."""
        if time() - self._last_pruned < self.ttl:
            return
        self.cache = {
            k: (v, time_entered)
            for k, (v, time_entered) in self.cache.items()
            if time_entered > (time() - self.ttl)
        }
        self._last_pruned = time()

    @staticmethod
    def _key_str(key: Any) -> str:
        """Get a string representation of a key."""
        return key if len(str(key)) < 10 else f"{str(key)[:9]}..."


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
            obj = obj.get(key, default)
        return obj
    except (AttributeError, KeyError, TypeError):
        return default
