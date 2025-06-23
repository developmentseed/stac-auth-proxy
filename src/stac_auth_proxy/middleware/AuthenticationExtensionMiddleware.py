"""Middleware to add auth information to item response served by upstream API."""

import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Scope

from ..config import EndpointMethods
from ..utils.middleware import JsonResponseMiddleware
from ..utils.requests import find_match
from ..utils.stac import get_links

logger = logging.getLogger(__name__)


@dataclass
class AuthenticationExtensionMiddleware(JsonResponseMiddleware):
    """Middleware to add the authentication extension to the response."""

    app: ASGIApp

    default_public: bool
    private_endpoints: EndpointMethods
    public_endpoints: EndpointMethods

    oidc_discovery_url: str
    auth_scheme_name: str = "oidc"
    auth_scheme: dict[str, Any] = field(default_factory=dict)
    extension_url: str = (
        "https://stac-extensions.github.io/authentication/v1.1.0/schema.json"
    )

    json_content_type_expr: str = r"application/(geo\+)?json"

    def should_transform_response(self, request: Request, scope: Scope) -> bool:
        """Determine if the response should be transformed."""
        # Match STAC catalog, collection, or item URLs with a single regex
        return (
            all(
                (
                    re.match(expr, val)
                    for expr, val in [
                        (
                            # catalog, collections, collection, items, item, search
                            r"^(/|/collections(/[^/]+(/items(/[^/]+)?)?)?|/search)$",
                            request.url.path,
                        ),
                        (
                            self.json_content_type_expr,
                            Headers(scope=scope).get("content-type", ""),
                        ),
                    ]
                ),
            )
            and 200 <= scope["status"] < 300
        )

    def transform_json(self, data: dict[str, Any], request: Request) -> dict[str, Any]:
        """Augment the STAC Item with auth information."""
        extensions = data.setdefault("stac_extensions", [])
        if self.extension_url not in extensions:
            extensions.append(self.extension_url)

        # auth:schemes
        # ---
        # A property that contains all of the scheme definitions used by Assets and
        # Links in the STAC Item or Collection.
        # - Catalogs
        # - Collections
        # - Item Properties

        scheme_loc = data["properties"] if "properties" in data else data
        schemes = scheme_loc.setdefault("auth:schemes", {})
        schemes[self.auth_scheme_name] = {
            "type": "openIdConnect",
            "openIdConnectUrl": self.oidc_discovery_url,
        }

        # auth:refs
        # ---
        # Annotate links with "auth:refs": [auth_scheme]
        for link in get_links(data):
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

        return data
