"""Reusable lifespan handler for FastAPI applications."""

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import HttpUrl
from starlette.middleware import Middleware

from .config import Settings

logger = logging.getLogger(__name__)
__all__ = ["build_lifespan", "check_conformance", "check_server_health"]


async def check_server_healths(*urls: str | HttpUrl) -> None:
    """Wait for upstream APIs to become available."""
    logger.info("Running upstream server health checks...")
    for url in urls:
        await check_server_health(url)
    logger.info(
        "Upstream servers are healthy:\n%s",
        "\n".join([f" - {url}" for url in urls]),
    )


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


def build_lifespan(settings: Settings | None = None, **settings_kwargs: Any):
    """
    Create a lifespan handler that runs startup checks.

    Parameters
    ----------
    settings : Settings | None, optional
        Pre-built settings instance. If omitted, a new one is constructed from
        ``settings_kwargs``.
    **settings_kwargs : Any
        Keyword arguments used to configure the health and conformance checks if
        ``settings`` is not provided.

    Returns
    -------
    Callable[[FastAPI], AsyncContextManager[Any]]
        A callable suitable for the ``lifespan`` parameter of ``FastAPI``.

    """
    if settings is None:
        settings = Settings(**settings_kwargs)

    @asynccontextmanager
    async def lifespan(app: "FastAPI"):
        assert settings is not None  # Required for type checking

        # Wait for upstream servers to become available
        if settings.wait_for_upstream:
            await check_server_healths(
                settings.upstream_url, settings.oidc_discovery_internal_url
            )

        # Log all middleware connected to the app
        logger.info(
            "Connected middleware:\n%s",
            "\n".join([f" - {m.cls.__name__}" for m in app.user_middleware]),
        )

        if settings.check_conformance:
            await check_conformance(app.user_middleware, str(settings.upstream_url))

        yield

    return lifespan
