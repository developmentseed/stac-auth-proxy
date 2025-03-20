"""Middleware to add auth information to item response served by upstream API."""

import re
from dataclasses import dataclass
from typing import Any

from starlette.requests import Request
from starlette.types import ASGIApp

from ..utils.filters import is_item_endpoint
from ..utils.middleware import JsonResponseMiddleware


@dataclass(frozen=True)
class AuthenticationExtensionMiddleware(JsonResponseMiddleware):
    """Middleware to add the authentication extension to the response."""

    app: ASGIApp
    endpoint: str
    asset_expression: str

    def should_transform_response(self, request: Request) -> bool:
        """Only transform responses for STAC Items."""
        return is_item_endpoint(request.url.path)

    def transform_json(self, item: dict[str, Any]) -> dict[str, Any]:
        """Augment the STAC Item with auth information."""
        extension = (
            "https://stac-extensions.github.io/authentication/v1.1.0/schema.json"
        )
        extensions = item.setdefault("stac_extensions", [])
        if extension not in extensions:
            extensions.append(extension)

        # TODO: Should we add this to items even if the assets don't match the asset expression?
        schemes = item["properties"].setdefault("auth:schemes", {})
        scheme = "signed_url_auth"
        schemes[scheme] = {
            "type": "signedUrl",
            "description": "Requires an authentication API",
            "flows": {
                "authorizationCode": {
                    "authorizationApi": self.endpoint,
                    "method": "POST",
                    "parameters": {
                        "bucket": {
                            "in": "body",
                            "required": True,
                            "description": "asset bucket",
                            "schema": {
                                "type": "string",
                                "examples": "example-bucket",
                            },
                        },
                        "key": {
                            "in": "body",
                            "required": True,
                            "description": "asset key",
                            "schema": {
                                "type": "string",
                                "examples": "path/to/example/asset.xyz",
                            },
                        },
                    },
                    "responseField": "signed_url",
                }
            },
        }

        for asset in item["assets"].values():
            if re.match(self.asset_expression, asset.get("href", "")):
                asset.setdefault("auth:refs", []).append(scheme)
        return item
