"""Integration with Open Policy Agent (OPA) to generate CQL2 filters for requests to a STAC API."""

from dataclasses import dataclass, field
from typing import Any

import httpx

from ..utils.cache import MemoryCache, get_value_by_path


@dataclass
class Opa:
    """Call Open Policy Agent (OPA) to generate CQL2 filters from request context."""

    host: str
    decision: str

    client: httpx.AsyncClient = field(init=False)
    cache: MemoryCache = field(init=False)
    cache_key: str = "req.headers.authorization"
    cache_ttl: float = 5.0

    def __post_init__(self):
        """Initialize the client."""
        self.client = httpx.AsyncClient(base_url=self.host)
        self.cache = MemoryCache(ttl=self.cache_ttl)

    async def __call__(self, context: dict[str, Any]) -> str:
        """Generate a CQL2 filter for the request."""
        token = get_value_by_path(context, self.cache_key)
        try:
            expr_str = self.cache[token]
        except KeyError:
            expr_str = await self._fetch(context)
            self.cache[token] = expr_str
        return expr_str

    async def _fetch(self, context: dict[str, Any]) -> str:
        """Fetch the CQL2 filter from OPA."""
        response = await self.client.post(
            f"/v1/data/{self.decision}",
            json={"input": context},
        )
        return response.raise_for_status().json()["result"]
