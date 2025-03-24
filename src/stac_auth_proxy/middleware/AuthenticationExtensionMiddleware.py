"""Middleware to add auth information to item response served by upstream API."""

import logging
import re
from dataclasses import dataclass, field
from itertools import chain
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from pydantic import HttpUrl
from starlette.requests import Request
from starlette.types import ASGIApp

from ..config import EndpointMethods
from ..utils.middleware import JsonResponseMiddleware
from ..utils.requests import find_match

logger = logging.getLogger(__name__)


@dataclass
class AuthenticationExtensionMiddleware(JsonResponseMiddleware):
    """Middleware to add the authentication extension to the response."""

    app: ASGIApp

    signing_endpoint: Optional[str]
    signed_asset_expression: str

    default_public: bool
    private_endpoints: EndpointMethods
    public_endpoints: EndpointMethods

    oidc_config_url: Optional[HttpUrl] = None
    signing_scheme_name: str = "signed_url_auth"
    auth_scheme_name: str = "oauth"
    auth_scheme: dict[str, Any] = field(default_factory=dict)
    extension_url: str = (
        "https://stac-extensions.github.io/authentication/v1.1.0/schema.json"
    )

    def __post_init__(self):
        """Load after initialization."""
        if self.oidc_config_url and not self.auth_scheme:
            # Retrieve OIDC configuration and extract authorization and token URLs
            oidc_config = httpx.get(str(self.oidc_config_url)).json()
            self.auth_scheme = {
                "type": "oauth2",
                "description": "requires an authentication token",
                "flows": {
                    "authorizationCode": {
                        "authorizationUrl": oidc_config.get("authorization_endpoint"),
                        "tokenUrl": oidc_config.get("token_endpoint"),
                        "scopes": {
                            k: k
                            for k in sorted(oidc_config.get("scopes_supported", []))
                        },
                    },
                },
            }

    def should_transform_response(self, request: Request) -> bool:
        """Determine if the response should be transformed."""
        # Match STAC catalog, collection, or item URLs with a single regex
        return bool(
            re.match(
                # catalog, collections, collection, items, item, search
                r"^(/|/collections(/[^/]+(/items(/[^/]+)?)?)?|/search)$",
                request.url.path,
            )
        )

    def transform_json(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Augment the STAC Item with auth information."""
        extensions = doc.setdefault("stac_extensions", [])
        if self.extension_url not in extensions:
            extensions.append(self.extension_url)

        # TODO: Should we add this to items even if the assets don't match the asset expression?
        # auth:schemes
        # ---
        # A property that contains all of the scheme definitions used by Assets and
        # Links in the STAC Item or Collection.
        # - Catalogs
        # - Collections
        # - Item Properties
        scheme_loc = doc["properties"] if "properties" in doc else doc
        schemes = scheme_loc.setdefault("auth:schemes", {})
        schemes[self.auth_scheme_name] = self.auth_scheme
        if self.signing_endpoint:
            schemes[self.signing_scheme_name] = {
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
            assets = chain(
                # Item
                doc.get("assets", {}).values(),
                # Items/Search
                (
                    asset
                    for item in doc.get("features", [])
                    for asset in item.get("assets", {}).values()
                ),
            )
            for asset in assets:
                if "href" not in asset:
                    logger.warning("Asset %s has no href", asset)
                    continue
                if re.match(self.signed_asset_expression, asset["href"]):
                    asset.setdefault("auth:refs", []).append(self.signing_scheme_name)

        # Annotate links with "auth:refs": [auth_scheme]
        links = chain(
            # Item/Collection
            doc.get("links", []),
            # Collections/Items/Search
            (
                link
                for prop in ["features", "collections"]
                for object_with_links in doc.get(prop, [])
                for link in object_with_links.get("links", [])
            ),
        )
        for link in links:
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
                link.setdefault("auth:refs", []).append(self.auth_scheme_name)

        return doc
