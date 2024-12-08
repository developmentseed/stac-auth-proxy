"""
STAC Auth Proxy API.

This module defines the FastAPI application for the STAC Auth Proxy, which handles
authentication, authorization, and proxying of requests to some internal STAC API.
"""

import logging
from typing import Optional

from eoapi.auth_utils import OpenIdConnectAuth
from fastapi import Depends, FastAPI

from .config import Settings
from .handlers import OpenApiSpecHandler, ReverseProxyHandler
from .middleware import AddProcessTimeHeaderMiddleware

logger = logging.getLogger(__name__)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """FastAPI Application Factory."""
    settings = settings or Settings()

    app = FastAPI(openapi_url=None)
    app.add_middleware(AddProcessTimeHeaderMiddleware)

    auth_scheme = OpenIdConnectAuth(
        openid_configuration_url=str(settings.oidc_discovery_url)
    ).valid_token_dependency

    if settings.guard:
        logger.info("Wrapping auth scheme")
        auth_scheme = settings.guard(auth_scheme)

    proxy_handler = ReverseProxyHandler(upstream=str(settings.upstream_url))
    openapi_handler = OpenApiSpecHandler(
        proxy=proxy_handler, oidc_config_url=str(settings.oidc_discovery_url)
    )

    # Endpoints that are explicitely marked private
    for path, methods in settings.private_endpoints.items():
        app.add_api_route(
            path,
            (
                proxy_handler.stream
                if path != settings.openapi_spec_endpoint
                else openapi_handler.dispatch
            ),
            methods=methods,
            dependencies=[Depends(auth_scheme)],
        )

    # Endpoints that are explicitely marked as public
    for path, methods in settings.public_endpoints.items():
        app.add_api_route(
            path,
            (
                proxy_handler.stream
                if path != settings.openapi_spec_endpoint
                else openapi_handler.dispatch
            ),
            methods=methods,
        )

    if settings.debug:
        app.add_api_route(
            "/_debug",
            lambda: {"settings": settings},
            methods=["GET"],
        )

    # Catchall for remainder of the endpoints
    app.add_api_route(
        "/{path:path}",
        proxy_handler.stream,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        dependencies=([] if settings.default_public else [Depends(auth_scheme)]),
    )

    return app
