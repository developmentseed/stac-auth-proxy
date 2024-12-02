"""
STAC Auth Proxy API.

This module defines the FastAPI application for the STAC Auth Proxy, which handles
authentication, authorization, and proxying of requests to some internal STAC API.
"""

from typing import Optional

from fastapi import Depends, FastAPI
from fastapi.security import OpenIdConnect

from .config import Settings
from .handlers import OpenApiSpecHandler
from .middleware import AddProcessTimeHeaderMiddleware
from .proxy import ReverseProxy


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """FastAPI Application Factory."""
    settings = settings or Settings()

    app = FastAPI(openapi_url=None)
    app.add_middleware(AddProcessTimeHeaderMiddleware)

    auth_scheme = OpenIdConnect(
        openIdConnectUrl=str(settings.oidc_discovery_url),
        scheme_name="OpenID Connect",
        description="OpenID Connect authentication for STAC API access",
    )

    proxy = ReverseProxy(upstream=str(settings.upstream_url))

    openapi_handler = OpenApiSpecHandler(
        proxy=proxy, oidc_config_url=str(settings.oidc_discovery_url)
    ).dispatch

    # Endpoints that are explicitely marked private
    for path, methods in settings.private_endpoints.items():
        app.add_api_route(
            path,
            (
                proxy.stream
                if path != settings.openapi_spec_endpoint
                else openapi_handler
            ),
            methods=methods,
            dependencies=[Depends(auth_scheme)],
        )

    # Endpoints that are explicitely marked as public
    for path, methods in settings.public_endpoints.items():
        app.add_api_route(
            path,
            (
                proxy.stream
                if path != settings.openapi_spec_endpoint
                else openapi_handler
            ),
            methods=methods,
        )

    # Catchall for remainder of the endpoints
    app.add_api_route(
        "/{path:path}",
        proxy.stream,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        dependencies=([] if settings.default_public else [Depends(auth_scheme)]),
    )

    return app
