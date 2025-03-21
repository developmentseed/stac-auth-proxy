"""Middleware to add auth information to item response served by upstream API."""

import logging
import re
from dataclasses import dataclass
from itertools import chain
from typing import Any, Optional
from urllib.parse import urlparse

from starlette.requests import Request
from starlette.types import ASGIApp

from ..config import EndpointMethods
from ..utils.middleware import JsonResponseMiddleware
from ..utils.requests import find_match

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthenticationExtensionMiddleware(JsonResponseMiddleware):
    """Middleware to add the authentication extension to the response."""

    app: ASGIApp

    signing_endpoint: Optional[str]
    signed_asset_expression: str

    default_public: bool
    private_endpoints: EndpointMethods
    public_endpoints: EndpointMethods

    signing_scheme: str = "signed_url_auth"
    auth_scheme: str = "oauth"

    def should_transform_response(self, request: Request) -> bool:
        """Determine if the response should be transformed."""
        print(f"{request.url=!s}")
        return True

    def transform_json(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Augment the STAC Item with auth information."""
        extension = (
            "https://stac-extensions.github.io/authentication/v1.1.0/schema.json"
        )
        extensions = doc.setdefault("stac_extensions", [])
        if extension not in extensions:
            extensions.append(extension)

        # TODO: Should we add this to items even if the assets don't match the asset expression?
        # auth:schemes
        # ---
        # A property that contains all of the scheme definitions used by Assets and
        # Links in the STAC Item or Collection.
        # - Catalogs
        # - Collections
        # - Item Properties
        # "auth:schemes": {
        #   "oauth": {
        #     "type": "oauth2",
        #     "description": "requires a login and user token",
        #     "flows": {
        #       "authorizationUrl": "https://example.com/oauth/authorize",
        #       "tokenUrl": "https://example.com/oauth/token",
        #       "scopes": {}
        #     }
        #   }
        # }
        # TODO: Add directly to Collections & Catalogs doc
        if "properties" in doc:
            schemes = doc["properties"].setdefault("auth:schemes", {})
            schemes[self.auth_scheme] = {
                "type": "oauth2",
                "description": "requires a login and user token",
                "flows": {
                    # TODO: Get authorizationUrl and tokenUrl from config
                    "authorizationCode": {
                        "authorizationUrl": "https://example.com/oauth/authorize",
                        "tokenUrl": "https://example.com/oauth/token",
                        "scopes": {},
                    },
                },
            }
            if self.signing_endpoint:
                schemes[self.signing_scheme] = {
                    "type": "signedUrl",
                    "description": "Requires an authentication API",
                    "flows": {
                        "authorizationCode": {
                            "authorizationApi": self.signing_endpoint,
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

        # auth:refs
        # ---
        # Annotate assets with "auth:refs": [signing_scheme]
        if self.signing_endpoint:
            for asset in doc.get("assets", {}).values():
                if "href" not in asset:
                    logger.warning("Asset %s has no href", asset)
                    continue
                if re.match(self.signed_asset_expression, asset["href"]):
                    asset.setdefault("auth:refs", []).append(self.signing_scheme)

        # Annotate links with "auth:refs": [auth_scheme]
        links = chain(
            doc.get("links", []),
            (
                link
                for prop in ["features", "collections"]
                for object_with_links in doc.get(prop, [])
                for link in object_with_links.get("links", [])
            ),
        )
        for link in links:
            print(f"{link['href']=!s}")
            if "href" not in link:
                logger.warning("Link %s has no href", link)
                continue
            match = find_match(
                path=urlparse(link["href"]).path,
                method="GET",
                private_endpoints=self.private_endpoints,
                public_endpoints=self.public_endpoints,
                default_public=self.default_public,
            )
            if match.is_private:
                link.setdefault("auth:refs", []).append(self.auth_scheme)

        return doc
