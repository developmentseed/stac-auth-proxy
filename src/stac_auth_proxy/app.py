"""
STAC Auth Proxy API.

This module defines the FastAPI application for the STAC Auth Proxy, which handles
authentication, authorization, and proxying of requests to some internal STAC API.
"""

import logging
from typing import Optional

from fastapi import FastAPI

from .middleware import (
    OpenApiMiddleware,
    AddProcessTimeHeaderMiddleware,
    EnforceAuthMiddleware,
)

from .config import Settings
from .handlers import ReverseProxyHandler

logger = logging.getLogger(__name__)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """FastAPI Application Factory."""
    settings = settings or Settings()

    app = FastAPI(
        openapi_url=None,  # Disable OpenAPI schema endpoint, we want to serve upstream's schema
    )

    app.add_middleware(AddProcessTimeHeaderMiddleware)
    app.add_middleware(
        EnforceAuthMiddleware,
        public_endpoints=settings.public_endpoints,
        private_endpoints=settings.private_endpoints,
        default_public=settings.default_public,
        oidc_config_url=settings.oidc_discovery_url,
    )

    if settings.openapi_spec_endpoint:
        app.add_middleware(
            OpenApiMiddleware,
            openapi_spec_path=settings.openapi_spec_endpoint,
            oidc_config_url=str(settings.oidc_discovery_url),
            private_endpoints=settings.private_endpoints,
            default_public=settings.default_public,
        )

    if settings.debug:
        app.add_api_route(
            "/_debug",
            lambda: {"settings": settings},
            methods=["GET"],
        )

    # Tooling
    proxy_handler = ReverseProxyHandler(
        upstream=str(settings.upstream_url),
        # TODO: Refactor filter tooling into middleare
        collections_filter=settings.collections_filter,
        items_filter=settings.items_filter,
    )

    # Configure security dependency for explicitely specified endpoints
    # for path_methods, dependencies in [
    #     (settings.private_endpoints, [Security(auth_scheme.validated_user)]),
    #     (settings.public_endpoints, []),
    # ]:
    #     for path, methods in path_methods.items():
    #         endpoint = (
    #             openapi_handler
    #             if path == settings.openapi_spec_endpoint
    #             else proxy_handler.stream
    #         )
    #         app.add_api_route(
    #             path,
    #             endpoint=endpoint,
    #             methods=methods,
    #             dependencies=dependencies,
    #         )

    # Catchall for remainder of the endpoints
    app.add_api_route(
        "/{path:path}",
        proxy_handler.stream,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    )

    return app
