"""
STAC Auth Proxy API.

This module defines the FastAPI application for the STAC Auth Proxy, which handles
authentication, authorization, and proxying of requests to some internal STAC API.
"""

import logging
from typing import Any, Optional

from fastapi import FastAPI
from starlette_cramjam.middleware import CompressionMiddleware

from .config import Settings
from .handlers import HealthzHandler, ReverseProxyHandler, SwaggerUI
from .lifespan import build_lifespan
from .middleware import (
    AddProcessTimeHeaderMiddleware,
    AuthenticationExtensionMiddleware,
    Cql2ApplyFilterBodyMiddleware,
    Cql2ApplyFilterQueryStringMiddleware,
    Cql2BuildFilterMiddleware,
    Cql2RewriteLinksFilterMiddleware,
    Cql2ValidateResponseBodyMiddleware,
    EnforceAuthMiddleware,
    OpenApiMiddleware,
    ProcessLinksMiddleware,
    RemoveRootPathMiddleware,
)

logger = logging.getLogger(__name__)


def configure_app(
    app: FastAPI,
    settings: Optional[Settings] = None,
    **settings_kwargs: Any,
) -> FastAPI:
    """
    Apply routes and middleware to a FastAPI app.

    Parameters
    ----------
    app : FastAPI
        The FastAPI app to configure.
    settings : Settings | None, optional
        Pre-built settings instance. If omitted, a new one is constructed from
        ``settings_kwargs``.
    **settings_kwargs : Any
        Keyword arguments used to configure the health and conformance checks if
        ``settings`` is not provided.

    """
    settings = settings or Settings(**settings_kwargs)

    #
    # Route Handlers
    #

    # If we have customized Swagger UI Init settings (e.g. a provided client_id)
    # then we need to serve our own Swagger UI in place of the upstream's. This requires
    # that we know the Swagger UI endpoint and the OpenAPI spec endpoint.
    if all(
        [
            settings.swagger_ui_endpoint,
            settings.openapi_spec_endpoint,
            settings.swagger_ui_init_oauth,
        ]
    ):
        app.add_route(
            settings.swagger_ui_endpoint,
            SwaggerUI(
                openapi_url=settings.openapi_spec_endpoint,  # type: ignore
                init_oauth=settings.swagger_ui_init_oauth,
            ).route,
            include_in_schema=False,
        )

    if settings.healthz_prefix:
        app.include_router(
            HealthzHandler(upstream_url=str(settings.upstream_url)).router,
            prefix=settings.healthz_prefix,
        )

    #
    # Middleware (order is important, last added = first to run)
    #

    if settings.enable_authentication_extension:
        app.add_middleware(
            AuthenticationExtensionMiddleware,
            default_public=settings.default_public,
            public_endpoints=settings.public_endpoints,
            private_endpoints=settings.private_endpoints,
            oidc_discovery_url=str(settings.oidc_discovery_url),
        )

    if settings.openapi_spec_endpoint:
        app.add_middleware(
            OpenApiMiddleware,
            openapi_spec_path=settings.openapi_spec_endpoint,
            oidc_discovery_url=str(settings.oidc_discovery_url),
            public_endpoints=settings.public_endpoints,
            private_endpoints=settings.private_endpoints,
            default_public=settings.default_public,
            root_path=settings.root_path,
            auth_scheme_name=settings.openapi_auth_scheme_name,
            auth_scheme_override=settings.openapi_auth_scheme_override,
        )

    if settings.items_filter or settings.collections_filter:
        app.add_middleware(Cql2ValidateResponseBodyMiddleware)
        app.add_middleware(Cql2ApplyFilterBodyMiddleware)
        app.add_middleware(Cql2ApplyFilterQueryStringMiddleware)
        app.add_middleware(Cql2RewriteLinksFilterMiddleware)
        app.add_middleware(
            Cql2BuildFilterMiddleware,
            items_filter=settings.items_filter() if settings.items_filter else None,
            collections_filter=(
                settings.collections_filter() if settings.collections_filter else None
            ),
            collections_filter_path=settings.collections_filter_path,
            items_filter_path=settings.items_filter_path,
        )

    app.add_middleware(
        AddProcessTimeHeaderMiddleware,
    )

    app.add_middleware(
        EnforceAuthMiddleware,
        public_endpoints=settings.public_endpoints,
        private_endpoints=settings.private_endpoints,
        default_public=settings.default_public,
        oidc_discovery_url=settings.oidc_discovery_internal_url,
        allowed_jwt_audiences=settings.allowed_jwt_audiences,
    )

    if settings.root_path or settings.upstream_url.path != "/":
        app.add_middleware(
            ProcessLinksMiddleware,
            upstream_url=str(settings.upstream_url),
            root_path=settings.root_path,
        )

    if settings.root_path:
        app.add_middleware(
            RemoveRootPathMiddleware,
            root_path=settings.root_path,
        )

    if settings.enable_compression:
        app.add_middleware(
            CompressionMiddleware,
        )

    return app


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """FastAPI Application Factory."""
    settings = settings or Settings()

    app = FastAPI(
        openapi_url=None,  # Disable OpenAPI schema endpoint, we want to serve upstream's schema
        lifespan=build_lifespan(settings=settings),
        root_path=settings.root_path,
    )
    if app.root_path:
        logger.debug("Mounted app at %s", app.root_path)

    configure_app(app, settings)

    app.add_api_route(
        "/{path:path}",
        ReverseProxyHandler(
            upstream=str(settings.upstream_url),
            override_host=settings.override_host,
        ).proxy_request,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    return app
