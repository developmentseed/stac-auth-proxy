from stac_auth_proxy.config import EndpointMethods
from stac_auth_proxy.utils.requests import dict_to_bytes


from starlette.types import ASGIApp, Message, Receive, Scope, Send


import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OpenApiMiddleware:
    """Middleware to add the OpenAPI spec to the response."""

    app: ASGIApp
    openapi_spec_path: str
    oidc_config_url: str
    private_endpoints: EndpointMethods
    default_public: bool
    oidc_auth_scheme_name: str = "oidcAuth"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Add the OpenAPI spec to the response."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def augment_oidc_spec(message: Message):
            if message["type"] != "http.response.body":
                return await send(message)

            # TODO: Make more robust to handle non-JSON responses
            body = json.loads(message["body"])

            await send(
                {
                    "type": "http.response.body",
                    "body": dict_to_bytes(self.augment_spec(body)),
                }
            )

        return await self.app(scope, receive, augment_oidc_spec)

    def augment_spec(self, openapi_spec) -> dict[str, Any]:
        components = openapi_spec.setdefault("components", {})
        securitySchemes = components.setdefault("securitySchemes", {})
        securitySchemes[self.oidc_auth_scheme_name] = {
            "type": "openIdConnect",
            "openIdConnectUrl": self.oidc_config_url,
        }
        for path, method_config in openapi_spec["paths"].items():
            for method, config in method_config.items():
                for private_method in self.private_endpoints.get(path, []):
                    if method.lower() == private_method.lower():
                        config.setdefault("security", []).append(
                            {self.oidc_auth_scheme_name: []}
                        )
        return openapi_spec
