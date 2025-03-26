"""Health check implementations for lifespan events."""

import asyncio
import logging

import httpx
from pydantic import HttpUrl

logger = logging.getLogger(__name__)


async def check_server_health(
    url: str | HttpUrl,
    max_retries: int = 10,
    retry_delay: float = 1.0,
    retry_delay_max: float = 5.0,
    timeout: float = 5.0,
) -> None:
    """Wait for upstream API to become available."""
    # Convert url to string if it's a HttpUrl
    if isinstance(url, HttpUrl):
        url = str(url)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for attempt in range(max_retries):
            try:
                response = await client.get(url)
                response.raise_for_status()
                logger.info(f"Upstream API {url!r} is healthy")
                return
            except Exception as e:
                logger.warning(f"Upstream health check for {url!r} failed: {e}")
                retry_in = min(retry_delay * (2**attempt), retry_delay_max)
                logger.warning(
                    f"Upstream API {url!r} not healthy, retrying in {retry_in:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(retry_in)

    raise RuntimeError(
        f"Upstream API {url!r} failed to respond after {max_retries} attempts"
    )
