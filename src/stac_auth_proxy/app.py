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
from .handlers import HealthzHandler, ReverseProxyHandler, SwaggerUI
from .middleware import (
    AddProcessTimeHeaderMiddleware,
    ApplyCql2FilterMiddleware,
    AuthenticationExtensionMiddleware,
    BuildCql2FilterMiddleware,
    EnforceAuthMiddleware,
    OpenApiMiddleware,
    ProcessLinksMiddleware,
    RemoveRootPathMiddleware,
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
        root_path=settings.root_path,
    )
    if app.root_path:
        logger.debug("Mounted app at %s", app.root_path)

    #
    # Handlers (place catch-all proxy handler last)
    #

    if settings.swagger_ui_endpoint:
        assert (
            settings.openapi_spec_endpoint
        ), "openapi_spec_endpoint must be set when using swagger_ui_endpoint"
        app.add_route(
            settings.swagger_ui_endpoint,
            SwaggerUI(
                openapi_url=settings.openapi_spec_endpoint,
                init_oauth=settings.swagger_ui_init_oauth,
            ).route,
            include_in_schema=False,
        )
    if settings.healthz_prefix:
        app.include_router(
            HealthzHandler(upstream_url=str(settings.upstream_url)).router,
            prefix=settings.healthz_prefix,
        )

    app.add_api_route(
        "/{path:path}",
        ReverseProxyHandler(
            upstream=str(settings.upstream_url),
            override_host=settings.override_host,
        ).proxy_request,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
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
        app.add_middleware(
            ApplyCql2FilterMiddleware,
        )
        app.add_middleware(
            BuildCql2FilterMiddleware,
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
