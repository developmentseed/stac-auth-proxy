"""
STAC Auth Proxy API.

This module defines the FastAPI application for the STAC Auth Proxy, which handles
authentication, authorization, and proxying of requests to some internal STAC API.
"""

import logging
from typing import Optional

from fastapi import FastAPI
from starlette_cramjam.middleware import CompressionMiddleware

from .config import Settings
from .handlers import HealthzHandler, ReverseProxyHandler
from .lifespan import LifespanManager, ServerHealthCheck
from .middleware import (
    AddProcessTimeHeaderMiddleware,
    ApplyCql2FilterMiddleware,
    BuildCql2FilterMiddleware,
    EnforceAuthMiddleware,
    OpenApiMiddleware,
)

logger = logging.getLogger(__name__)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """FastAPI Application Factory."""
    settings = settings or Settings()

    #
    # Application
    #
    upstream_urls = (
        [settings.upstream_url, settings.oidc_discovery_internal_url]
        if settings.wait_for_upstream
        else []
    )
    lifespan = LifespanManager(
        on_startup=([ServerHealthCheck(url=url) for url in upstream_urls])
    )

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
        EnforceAuthMiddleware,
        public_endpoints=settings.public_endpoints,
        private_endpoints=settings.private_endpoints,
        default_public=settings.default_public,
        oidc_config_url=settings.oidc_discovery_internal_url,
    )

    app.add_middleware(
        CompressionMiddleware,
    )

    app.add_middleware(
        AddProcessTimeHeaderMiddleware,
    )

    return app
