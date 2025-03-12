"""
STAC Auth Proxy API.

This module defines the FastAPI application for the STAC Auth Proxy, which handles
authentication, authorization, and proxying of requests to some internal STAC API.
"""

import logging
from typing import Optional

from fastapi import FastAPI

from .config import Settings
from .handlers import HealthzHandler, ReverseProxyHandler
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

    app = FastAPI(
        openapi_url=None,  # Disable OpenAPI schema endpoint, we want to serve upstream's schema
    )

    app.add_middleware(AddProcessTimeHeaderMiddleware)

    if settings.openapi_spec_endpoint:
        app.add_middleware(
            OpenApiMiddleware,
            openapi_spec_path=settings.openapi_spec_endpoint,
            oidc_config_url=str(settings.oidc_discovery_url),
            private_endpoints=settings.private_endpoints,
            default_public=settings.default_public,
        )

    if settings.items_filter:
        app.add_middleware(ApplyCql2FilterMiddleware)
        app.add_middleware(
            BuildCql2FilterMiddleware,
            # collections_filter=settings.collections_filter,
            items_filter=settings.items_filter(),
        )

    app.add_middleware(
        EnforceAuthMiddleware,
        public_endpoints=settings.public_endpoints,
        private_endpoints=settings.private_endpoints,
        default_public=settings.default_public,
        oidc_config_url=settings.oidc_discovery_url,
    )

    if settings.healthz_prefix:
        healthz_handler = HealthzHandler(upstream_url=str(settings.upstream_url))
        app.include_router(healthz_handler.router, prefix="/healthz")

    # Catchall for any endpoint
    proxy_handler = ReverseProxyHandler(upstream=str(settings.upstream_url))
    app.add_api_route(
        "/{path:path}",
        proxy_handler.stream,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    )

    return app
