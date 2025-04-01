"""Middleware to add auth information to item response served by upstream API."""

import logging
import re
from dataclasses import dataclass, field
from itertools import chain
from typing import Any
from urllib.parse import urlparse

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Scope

from ..config import EndpointMethods
from ..utils.middleware import JsonResponseMiddleware
from ..utils.requests import find_match

logger = logging.getLogger(__name__)


@dataclass
class AuthenticationExtensionMiddleware(JsonResponseMiddleware):
    """Middleware to add the authentication extension to the response."""

    app: ASGIApp

    default_public: bool
    private_endpoints: EndpointMethods
    public_endpoints: EndpointMethods

    auth_scheme_name: str = "oauth"
    auth_scheme: dict[str, Any] = field(default_factory=dict)
    extension_url: str = (
        "https://stac-extensions.github.io/authentication/v1.1.0/schema.json"
    )

    json_content_type_expr: str = r"(application/json|geo\+json)"

    def should_transform_response(
        self, request: Request, response_headers: Headers
    ) -> bool:
        """Determine if the response should be transformed."""
        # Match STAC catalog, collection, or item URLs with a single regex
        return all(
            [
                re.match(
                    # catalog, collections, collection, items, item, search
                    r"^(/|/collections(/[^/]+(/items(/[^/]+)?)?)?|/search)$",
                    request.url.path,
                ),
                re.match(
                    self.json_content_type_expr,
                    response_headers.get("content-type", ""),
                ),
            ]
        )

    def transform_json(self, doc: dict[str, Any], scope: Scope) -> dict[str, Any]:
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

        if "oidc_metadata" not in scope:
            logger.error(
                "OIDC metadata not found in scope. "
                "Skipping authentication extension."
            )
            return doc

        scheme_loc = doc["properties"] if "properties" in doc else doc
        schemes = scheme_loc.setdefault("auth:schemes", {})
        schemes[self.auth_scheme_name] = self.parse_oidc_config(
            scope.get("oidc_metadata", {})
        )

        # auth:refs
        # ---
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

    def parse_oidc_config(self, oidc_config: dict[str, Any]) -> dict[str, Any]:
        """Parse the OIDC configuration."""
        return {
            "type": "oauth2",
            "description": "requires an authentication token",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": oidc_config["authorization_endpoint"],
                    "tokenUrl": oidc_config.get("token_endpoint"),
                    "scopes": {
                        k: k for k in sorted(oidc_config.get("scopes_supported", []))
                    },
                },
            },
        }
