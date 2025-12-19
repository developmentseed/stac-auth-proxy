"""STAC-specific utilities."""

import logging
from collections.abc import Callable
from itertools import chain
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def ensure_type(
    data: dict[str, Any],
    key: str,
    expected_type: type[T],
    default_factory: Callable[[], T] | None = None,
) -> T:
    """
    Ensure a dictionary value conforms to the expected type.

    If the value doesn't exist or is not an instance of the expected type,
    it will be replaced with the default value from default_factory.

    Args:
        data: The dictionary containing the value
        key: The key to check
        expected_type: The expected type class
        default_factory: Optional callable that returns the default value.
            If not provided, expected_type will be called with no arguments.

    Returns:
        The value from the dictionary if it's the correct type, otherwise the default value

    Example:
        >>> data = {"stac_extensions": None}
        >>> extensions = ensure_type(data, "stac_extensions", list)
        >>> # extensions is now [] and data["stac_extensions"] is []
        >>>
        >>> data = {"items": "invalid"}
        >>> items = ensure_type(data, "items", list, lambda: ["default"])
        >>> # items is now ["default"] with custom factory

    """
    value = data.get(key)
    if not isinstance(value, expected_type):
        if value is not None:
            logger.warning(
                "Field '%s' expected %s but got %s: %r",
                key,
                expected_type.__name__,
                type(value).__name__,
                value,
            )
        factory = default_factory if default_factory is not None else expected_type
        value = factory()
        data[key] = value
    return value


def get_links(data: dict) -> chain[dict]:
    """Get all links from a STAC response."""
    return chain(
        # Item/Collection
        data.get("links", []),
        # Collections/Items/Search
        (
            link
            for prop in ["features", "collections"]
            for object_with_links in data.get(prop, [])
            for link in object_with_links.get("links", [])
        ),
    )
