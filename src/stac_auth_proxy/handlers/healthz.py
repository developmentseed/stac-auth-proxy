"""Health check endpoints."""

from dataclasses import dataclass, field

from fastapi import APIRouter
from httpx import AsyncClient


@dataclass
class HealthzHandler:
    """Handler for health check endpoints."""

    upstream_url: str
    router: APIRouter = field(init=False)

    def __post_init__(self):
        """Initialize the router."""
        self.router = APIRouter()
        self.router.add_api_route("", self.healthz, methods=["GET"])
        self.router.add_api_route("/upstream", self.healthz_upstream, methods=["GET"])

    async def healthz(self):
        """Return health of this API."""
        return {"status": "ok"}

    async def healthz_upstream(self):
        """Return health of upstream STAC API."""
        async with AsyncClient() as client:
            response = await client.get(self.upstream_url)
            response.raise_for_status()
            return {"status": "ok", "code": response.status_code}
