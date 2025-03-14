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

    urls: list[str | HttpUrl]
    max_retries: int = 5
    retry_delay: float = 0.5
    retry_delay_max: float = 10.0
    timeout: float = 5.0

    def __post_init__(self):
        """Convert url to string if it's a HttpUrl."""
        self.urls = [str(url) if isinstance(url, HttpUrl) else url for url in self.urls]

    async def _check_health(self, url: str) -> bool:
        """Check if upstream API is responding."""
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        url, timeout=self.timeout, follow_redirects=True
                    )
                    response.raise_for_status()
                    logger.info(f"Upstream API {url!r} is healthy")
                    return True
            except Exception as e:
                logger.warning(f"Upstream health check for {url!r} failed: {e}")

            retry_in = min(self.retry_delay * (2**attempt), self.retry_delay_max)
            logger.warning(
                f"Upstream API {url!r} not healthy, retrying in {retry_in:.1f}s "
                f"(attempt {attempt + 1}/{self.max_retries})"
            )
            await asyncio.sleep(retry_in)

        raise RuntimeError(
            f"Upstream API {url!r} failed to respond after {self.max_retries} attempts"
        )

    async def __call__(self) -> None:
        """Wait for upstream API to become available."""
        for url in self.urls:
            await self._check_health(url)
