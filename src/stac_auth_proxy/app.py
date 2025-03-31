"""
STAC Auth Proxy API.

This module defines the FastAPI application for the STAC Auth Proxy, which handles
authentication, authorization, and proxying of requests to some internal STAC API.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from starlette_cramjam.middleware import CompressionMiddleware

from .config import Settings
from .handlers import HealthzHandler, ReverseProxyHandler
from .middleware import (
    AddProcessTimeHeaderMiddleware,
    ApplyCql2FilterMiddleware,
    AuthenticationExtensionMiddleware,
    BuildCql2FilterMiddleware,
    EnforceAuthMiddleware,
    OpenApiMiddleware,
)
from .utils.lifespan import check_conformance, check_server_health

logger = logging.getLogger(__name__)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """FastAPI Application Factory."""
    settings = settings or Settings()

    #
    # Application
    #

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        assert settings

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
            await check_conformance(
                app.user_middleware,
                str(settings.upstream_url),
            )

        yield

    app = FastAPI(
        openapi_url=None,  # Disable OpenAPI schema endpoint, we want to serve upstream's schema
        lifespan=lifespan,
    )

    #
    # Handlers (place catch-all proxy handler last)
    #
    if settings.healthz_prefix:
        app.include_router(
            HealthzHandler(upstream_url=str(settings.upstream_url)).router,
            prefix=settings.healthz_prefix,
        )

    app.add_api_route(
        "/{path:path}",
        ReverseProxyHandler(upstream=str(settings.upstream_url)).proxy_request,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    )

    #
    # Middleware (order is important, last added = first to run)
    #
    app.add_middleware(
        AuthenticationExtensionMiddleware,
        default_public=settings.default_public,
        public_endpoints=settings.public_endpoints,
        private_endpoints=settings.private_endpoints,
        oidc_config_url=settings.oidc_discovery_internal_url,
    )

    if settings.openapi_spec_endpoint:
        app.add_middleware(
            OpenApiMiddleware,
            openapi_spec_path=settings.openapi_spec_endpoint,
            oidc_config_url=str(settings.oidc_discovery_url),
            public_endpoints=settings.public_endpoints,
            private_endpoints=settings.private_endpoints,
            default_public=settings.default_public,
        )

    if settings.items_filter:
        app.add_middleware(
            ApplyCql2FilterMiddleware,
        )
        app.add_middleware(
            BuildCql2FilterMiddleware,
            items_filter=settings.items_filter(),
        )

    app.add_middleware(
        CompressionMiddleware,
    )

    app.add_middleware(
        AddProcessTimeHeaderMiddleware,
    )

    app.add_middleware(
        EnforceAuthMiddleware,
        public_endpoints=settings.public_endpoints,
        private_endpoints=settings.private_endpoints,
        default_public=settings.default_public,
        oidc_config_url=settings.oidc_discovery_internal_url,
    )

    return app
