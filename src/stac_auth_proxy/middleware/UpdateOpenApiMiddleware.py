"""Middleware to add auth information to the OpenAPI spec served by upstream API."""

import json
from dataclasses import dataclass
from typing import Any, Optional

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..config import EndpointMethods
from ..utils.requests import dict_to_bytes, find_match


@dataclass(frozen=True)
class OpenApiMiddleware:
    """Middleware to add the OpenAPI spec to the response."""

    app: ASGIApp
    openapi_spec_path: str
    oidc_config_url: str
    private_endpoints: EndpointMethods
    public_endpoints: EndpointMethods
    default_public: bool
    oidc_auth_scheme_name: str = "oidcAuth"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Add the OpenAPI spec to the response."""
        if scope["type"] != "http" or Request(scope).url.path != self.openapi_spec_path:
            return await self.app(scope, receive, send)

        start_message: Optional[Message] = None
        body = b""

        async def augment_oidc_spec(message: Message):
            nonlocal start_message
            nonlocal body
            if message["type"] == "http.response.start":
                # NOTE: Because we are modifying the response body, we will need to update
                # the content-length header. However, headers are sent before we see the
                # body. To handle this, we delay sending the http.response.start message
                # until after we alter the body.
                start_message = message
                return
            elif message["type"] != "http.response.body":
                return await send(message)

            body += message["body"]

            # Skip body chunks until all chunks have been received
            if message.get("more_body"):
                return

            # Maybe decompress the body
            headers = MutableHeaders(scope=start_message)

            # Augment the spec
            body = dict_to_bytes(self.augment_spec(json.loads(body)))

            # Update the content-length header
            headers["content-length"] = str(len(body))
            assert start_message, "Expected start_message to be set"
            start_message["headers"] = [
                (key.encode(), value.encode()) for key, value in headers.items()
            ]

            # Send http.response.start
            await send(start_message)

            # Send http.response.body
            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                    "more_body": False,
                }
            )

        return await self.app(scope, receive, augment_oidc_spec)

    def augment_spec(self, openapi_spec) -> dict[str, Any]:
        """Augment the OpenAPI spec with auth information."""
        components = openapi_spec.setdefault("components", {})
        securitySchemes = components.setdefault("securitySchemes", {})
        securitySchemes[self.oidc_auth_scheme_name] = {
            "type": "openIdConnect",
            "openIdConnectUrl": self.oidc_config_url,
        }
        for path, method_config in openapi_spec["paths"].items():
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
                        {self.oidc_auth_scheme_name: match.required_scopes}
                    )
        return openapi_spec
