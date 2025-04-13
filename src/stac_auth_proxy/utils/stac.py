"""STAC-specific utilities."""

from itertools import chain


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
