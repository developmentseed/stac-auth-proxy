"""Health check implementations for lifespan events."""

import asyncio
import logging
from dataclasses import dataclass

import httpx
from pydantic import HttpUrl

logger = logging.getLogger(__name__)


@dataclass
class ServerHealthCheck:
    """Health check for upstream API."""

    url: str | HttpUrl
    max_retries: int = 5
    retry_delay: float = 0.25
    retry_delay_max: float = 10.0
    timeout: float = 5.0

    def __post_init__(self):
        """Convert url to string if it's a HttpUrl."""
        if isinstance(self.url, HttpUrl):
            self.url = str(self.url)

    async def _check_health(self) -> bool:
        """Check if upstream API is responding."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.url, timeout=self.timeout, follow_redirects=True
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.warning(f"Upstream health check for {self.url!r} failed: {e}")
            return False

    async def __call__(self) -> None:
        """Wait for upstream API to become available."""
        for attempt in range(self.max_retries):
            if await self._check_health():
                logger.info(f"Upstream API {self.url!r} is healthy")
                return

            retry_in = min(self.retry_delay * (2**attempt), self.retry_delay_max)
            logger.warning(
                f"Upstream API {self.url!r} not healthy, retrying in {retry_in:.1f}s "
                f"(attempt {attempt + 1}/{self.max_retries})"
            )
            await asyncio.sleep(retry_in)

        raise RuntimeError(
            f"Upstream API {self.url!r} failed to respond after {self.max_retries} attempts"
        )
