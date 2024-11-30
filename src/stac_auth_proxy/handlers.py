import logging
from dataclasses import dataclass

from fastapi import Request, Response
from fastapi.routing import APIRoute

from .proxy import ReverseProxy
from .utils import safe_headers

logger = logging.getLogger(__name__)


@dataclass
class OpenApiSpecHandler:
    proxy: ReverseProxy
    oidc_config_url: str
    auth_scheme_name: str = "oidcAuth"

    async def dispatch(self, req: Request, res: Response):
        """Proxy the OpenAPI spec from the upstream STAC API, updating it with OIDC security
        requirements.
        """
        oidc_spec_response = await self.proxy.proxy_request(req)
        openapi_spec = oidc_spec_response.json()

        # Pass along the response headers
        res.headers.update(safe_headers(oidc_spec_response.headers))

        # Add the OIDC security scheme to the components
        openapi_spec.setdefault("components", {}).setdefault("securitySchemes", {})[
            self.auth_scheme_name
        ] = {
            "type": "openIdConnect",
            "openIdConnectUrl": self.oidc_config_url,
        }

        proxy_auth_routes = [
            r
            for r in req.app.routes
            # Ignore non-APIRoutes (we can't check their security dependencies)
            if isinstance(r, APIRoute)
            # Ignore routes that don't have security requirements
            and (
                r.dependant.security_requirements
                or any(d.security_requirements for d in r.dependant.dependencies)
            )
        ]

        # Update the paths with the specified security requirements
        for path, method_config in openapi_spec["paths"].items():
            for method, config in method_config.items():
                for route in proxy_auth_routes:
                    match, _ = route.matches(
                        {"type": "http", "method": method.upper(), "path": path}
                    )
                    if match.name != "FULL":
                        continue
                    # Add the OIDC security requirement
                    config.setdefault("security", []).append(
                        [{self.auth_scheme_name: []}]
                    )
                    break

        return openapi_spec
