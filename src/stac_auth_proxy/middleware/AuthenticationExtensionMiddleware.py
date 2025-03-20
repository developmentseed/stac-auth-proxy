"""Middleware to add auth information to the OpenAPI spec served by upstream API."""

from dataclasses import dataclass, field
from typing import Any

from starlette.requests import Request
from starlette.types import ASGIApp

from ..utils.middleware import JsonResponseMiddleware


@dataclass(frozen=True)
class AuthenticationExtensionMiddleware(JsonResponseMiddleware):
    """Middleware to add the authentication extension to the response."""

    app: ASGIApp
    signers: dict[str, str] = field(default_factory=dict)

    def should_transform_response(self, request: Request) -> bool:
        """Only transform responses for STAC Items."""
        # TODO: Implement proper path matching for STAC Items
        return True

    def transform_json(self, item: dict[str, Any]) -> dict[str, Any]:
        """Augment the STAC Item with auth information."""
        # TODO: Implement STAC Item augmentation
        return item
