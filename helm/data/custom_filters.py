"""
Sample custom filters for STAC Auth Proxy.
This file demonstrates the structure needed for custom collection and item filters.
"""

import dataclasses
from typing import Any


@dataclasses.dataclass
class CollectionsFilter:
    """Filter collections based on user permissions."""

    async def __call__(self, context: dict[str, Any]) -> str:
        """Return True if user can access this collection."""
        # Example: Allow all collections for authenticated users
        return "1=1"


@dataclasses.dataclass
class ItemsFilter:
    """Filter items based on user permissions."""

    async def __call__(self, context: dict[str, Any]) -> str:
        """Return True if user can access this item."""
        # Example: Allow all items for authenticated users
        return "1=1"
