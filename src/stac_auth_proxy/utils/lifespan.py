"""Health check implementations for lifespan events."""

import asyncio
import logging
import re

import httpx
from pydantic import HttpUrl
from starlette.middleware import Middleware

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

    async with httpx.AsyncClient(
        base_url=url, timeout=timeout, follow_redirects=True
    ) as client:
        for attempt in range(max_retries):
            try:
                response = await client.get("/")
                response.raise_for_status()
                logger.info(f"Upstream API {url!r} is healthy")
                return
            except httpx.ConnectError as e:
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


async def check_conformance(
    middleware_classes: list[Middleware],
    api_url: str,
    attr_name: str = "__required_conformances__",
    endpoint: str = "/conformance",
):
    """Check if the upstream API supports a given conformance class."""
    required_conformances: dict[str, list[str]] = {}
    for middleware in middleware_classes:

        for conformance in getattr(middleware.cls, attr_name, []):
            required_conformances.setdefault(conformance, []).append(
                middleware.cls.__name__
            )

    async with httpx.AsyncClient(base_url=api_url) as client:
        response = await client.get(endpoint)
        response.raise_for_status()
        api_conforms_to = response.json().get("conformsTo", [])

    missing = [
        req_conformance
        for req_conformance in required_conformances.keys()
        if not any(
            re.match(req_conformance, conformance) for conformance in api_conforms_to
        )
    ]

    def conformance_str(conformance: str) -> str:
        return f" - {conformance} [{','.join(required_conformances[conformance])}]"

    if missing:
        missing_str = [conformance_str(c) for c in missing]
        raise RuntimeError(
            "\n".join(
                [
                    "Upstream catalog is missing the following conformance classes:",
                    *missing_str,
                ]
            )
        )
    logger.info(
        "Upstream catalog conforms to the following required conformance classes: \n%s",
        "\n".join([conformance_str(c) for c in required_conformances]),
    )
