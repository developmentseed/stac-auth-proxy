"""
STAC Auth Proxy API.

This module defines the FastAPI application for the STAC Auth Proxy, which handles
authentication, authorization, and proxying of requests to some internal STAC API.
"""

import logging
from typing import Optional

from fastapi import FastAPI, Security

from .auth import OpenIdConnectAuth
from .config import Settings
from .handlers import ReverseProxyHandler, build_openapi_spec_handler
from .middleware import AddProcessTimeHeaderMiddleware

logger = logging.getLogger(__name__)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """FastAPI Application Factory."""
    settings = settings or Settings()

    app = FastAPI(
        openapi_url=None,
    )
    app.add_middleware(AddProcessTimeHeaderMiddleware)

    auth_scheme = OpenIdConnectAuth(
        openid_configuration_url=settings.oidc_discovery_url
    )

    if settings.debug:
        app.add_api_route(
            "/_debug",
            lambda: {"settings": settings},
            methods=["GET"],
        )

    proxy_handler = ReverseProxyHandler(
        upstream=str(settings.upstream_url),
        auth_dependency=auth_scheme.maybe_validated_user,
        collections_filter=settings.collections_filter,
        items_filter=settings.items_filter,
    )
    openapi_handler = build_openapi_spec_handler(
        proxy=proxy_handler,
        oidc_config_url=str(settings.oidc_discovery_url),
    )
    # Endpoints that are explicitely marked private
    for path, methods in settings.private_endpoints.items():
        app.add_api_route(
            path,
            (
                proxy_handler.stream
                if path != settings.openapi_spec_endpoint
                else openapi_handler
            ),
            methods=methods,
            dependencies=[Security(auth_scheme.validated_user)],
        )

    # Endpoints that are explicitely marked as public
    for path, methods in settings.public_endpoints.items():
        app.add_api_route(
            path,
            (
                proxy_handler.stream
                if path != settings.openapi_spec_endpoint
                else openapi_handler
            ),
            methods=methods,
            dependencies=[Security(auth_scheme.maybe_validated_user)],
        )

    # Catchall for remainder of the endpoints
    app.add_api_route(
        "/{path:path}",
        proxy_handler.stream,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        dependencies=(
            [
                Security(
                    auth_scheme.maybe_validated_user
                    if settings.default_public
                    else auth_scheme.validated_user
                )
            ]
        ),
    )

    return app
