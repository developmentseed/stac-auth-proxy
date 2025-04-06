"""Integration with Open Policy Agent (OPA) to generate CQL2 filters for requests to a STAC API."""

import logging
from dataclasses import dataclass, field
from time import time
from typing import Any, Callable

import httpx

logger = logging.getLogger("stac_auth_proxy.opa_integration")


@dataclass
class cache:
    """Cache results of a method call for a given key."""

    key: Callable[[Any], Any]
    ttl: float = 5.0
    cache: dict[tuple[Any], tuple[Any, float]] = field(default_factory=dict)

    def __call__(self, func):
        """Decorate a function to cache its results."""

        async def wrapped(_self, ctx, *args, **kwargs):
            key = self.key(ctx)
            if key in self.cache:
                result, timestamp = self.cache[key]
                age = time() - timestamp
                if age <= self.ttl:
                    logger.debug("%r in cache, returning cached result", key)
                    return result
                logger.debug("%r in cache, but expired.", key)
            else:
                logger.debug("%r not in cache, calling function", key)
            result = await func(_self, ctx, *args, **kwargs)
            self.cache[key] = (result, time())
            self.prune()
            return result

        return wrapped

    def prune(self):
        """Prune the cache of expired items."""
        self.cache = {k: v for k, v in self.cache.items() if v[1] > time() - self.ttl}


@dataclass
class OpaIntegration:
    """Call Open Policy Agent (OPA) to generate CQL2 filters from request context."""

    host: str
    decision: str

    client: httpx.AsyncClient = field(init=False)

    def __post_init__(self):
        """Initialize the client."""
        self.client = httpx.AsyncClient(base_url=self.host)

    @cache(
        key=lambda ctx: ctx["payload"]["sub"] if ctx.get("payload") else None,
        ttl=10,
    )
    async def __call__(self, context: dict[str, Any]) -> str:
        """Generate a CQL2 filter for the request."""
        response = await self.client.post(
            f"/v1/data/{self.decision}",
            json={"input": context},
        )
        return response.raise_for_status().json()["result"]
