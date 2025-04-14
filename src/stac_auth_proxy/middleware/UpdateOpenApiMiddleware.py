"""Middleware to add auth information to the OpenAPI spec served by upstream API."""

import re
from dataclasses import dataclass
from typing import Any, Optional

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Scope

from ..config import EndpointMethods
from ..utils.middleware import JsonResponseMiddleware
from ..utils.requests import find_match


@dataclass(frozen=True)
class OpenApiMiddleware(JsonResponseMiddleware):
    """Middleware to add the OpenAPI spec to the response."""

    app: ASGIApp
    openapi_spec_path: str
    oidc_config_url: str
    private_endpoints: EndpointMethods
    public_endpoints: EndpointMethods
    default_public: bool
    auth_scheme_name: str = "oidcAuth"
    auth_scheme_override: Optional[dict] = None

    json_content_type_expr: str = r"application/(vnd\.oai\.openapi\+json?|json)"

    def should_transform_response(self, request: Request, scope: Scope) -> bool:
        """Only transform responses for the OpenAPI spec path."""
        return (
            all(
                re.match(expr, val)
                for expr, val in [
                    (self.openapi_spec_path, request.url.path),
                    (
                        self.json_content_type_expr,
                        Headers(scope=scope).get("content-type", ""),
                    ),
                ]
            )
            and 200 >= scope["status"] < 300
        )

    def transform_json(self, data: dict[str, Any], request: Request) -> dict[str, Any]:
        """Augment the OpenAPI spec with auth information."""
        components = data.setdefault("components", {})
        securitySchemes = components.setdefault("securitySchemes", {})
        securitySchemes[self.auth_scheme_name] = self.auth_scheme_override or {
            "type": "openIdConnect",
            "openIdConnectUrl": self.oidc_config_url,
        }
        for path, method_config in data["paths"].items():
            for method, config in method_config.items():
                match = find_match(
                    path,
                    method,
                    self.private_endpoints,
                    self.public_endpoints,
                    self.default_public,
                )
                if match.is_private:
                    config.setdefault("security", []).append(
                        {self.auth_scheme_name: match.required_scopes}
                    )
        return data
