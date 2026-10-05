"""Integration with Open Policy Agent (OPA) to generate CQL2 filters for requests to a STAC API."""

from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class Opa:
    """Call Open Policy Agent (OPA) to generate CQL2 filters from request context."""

    host: str
    decision: str

    client: httpx.AsyncClient = field(init=False)

    def __post_init__(self):
        """Initialize the client."""
        self.client = httpx.AsyncClient(base_url=self.host)

    async def __call__(self, context: dict[str, Any]) -> str:
        """
        Generate a CQL2 filter for the request.

        Not cached: the policy may depend on any part of the request (method,
        path, ...), so a result is only valid for the request it was computed for.
        """
        response = await self.client.post(
            f"/v1/data/{self.decision}",
            json={"input": context},
        )
        return response.raise_for_status().json()["result"]
