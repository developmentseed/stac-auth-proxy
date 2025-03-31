"""Integration with Open Policy Agent (OPA) to generate CQL2 filters for requests to a STAC API."""

import dataclasses
from typing import Any


@dataclasses.dataclass
class OpaIntegration:
    """Integration with Open Policy Agent (OPA) to generate CQL2 filters for requests to a STAC API."""

    async def __call__(self, context: dict[str, Any]) -> str:
        """Generate a CQL2 filter for the request."""
        return "(1=1)"
