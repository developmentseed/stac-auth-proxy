"""Reusable lifespan handler for FastAPI applications."""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI

from .config import Settings
from .utils.lifespan import check_conformance, check_server_health

logger = logging.getLogger(__name__)


def lifespan(settings: Settings | None = None):
    """Create a lifespan handler that runs startup checks.

    Parameters
    ----------
    settings : Settings | None
        Configuration for health and conformance checks. If omitted, default
        settings are loaded.

    Returns
    -------
    Callable[[FastAPI], AsyncContextManager[Any]]
        A callable suitable for the ``lifespan`` parameter of ``FastAPI``.
    """

    settings = settings or Settings()

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        # Wait for upstream servers to become available
        if settings.wait_for_upstream:
            logger.info("Running upstream server health checks...")
            urls = [settings.upstream_url, settings.oidc_discovery_internal_url]
            for url in urls:
                await check_server_health(url=url)
            logger.info(
                "Upstream servers are healthy:\n%s",
                "\n".join([f" - {url}" for url in urls]),
            )

        # Log all middleware connected to the app
        logger.info(
            "Connected middleware:\n%s",
            "\n".join([f" - {m.cls.__name__}" for m in app.user_middleware]),
        )

        if settings.check_conformance:
            await check_conformance(app.user_middleware, str(settings.upstream_url))

        yield

    return _lifespan


__all__ = ["lifespan"]

