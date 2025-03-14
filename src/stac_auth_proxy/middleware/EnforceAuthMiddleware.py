"""Middleware to enforce authentication."""

import logging
from dataclasses import dataclass
from typing import Annotated, Any, Optional, Sequence

import httpx
import jwt
from fastapi import HTTPException, Request, Security, status
from pydantic import HttpUrl
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ..config import EndpointMethods
from ..utils.requests import matches_route

logger = logging.getLogger(__name__)


@dataclass
class EnforceAuthMiddleware:
    """Middleware to enforce authentication."""

    app: ASGIApp
    private_endpoints: EndpointMethods
    public_endpoints: EndpointMethods
    default_public: bool

    oidc_config_url: HttpUrl
    oidc_config_internal_url: Optional[HttpUrl] = None
    allowed_jwt_audiences: Optional[Sequence[str]] = None

    state_key: str = "payload"

    # Generated attributes
    _jwks_client: Optional[jwt.PyJWKClient] = None

    @property
    def jwks_client(self) -> jwt.PyJWKClient:
        """Get the OIDC configuration URL."""
        if not self._jwks_client:
            logger.debug("Requesting OIDC config")
            origin_url = str(self.oidc_config_internal_url or self.oidc_config_url)

            try:
                response = httpx.get(origin_url)
                response.raise_for_status()
                oidc_config = response.json()
                self._jwks_client = jwt.PyJWKClient(oidc_config["jwks_uri"])
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Received a non-200 response when fetching OIDC config: %s",
                    e.response.text,
                )
                raise OidcFetchError(
                    f"Request for OIDC config failed with status {e.response.status_code}"
                ) from e
            except httpx.RequestError as e:
                logger.error(
                    "Error fetching OIDC config from %s: %s", origin_url, str(e)
                )
                raise OidcFetchError(f"Request for OIDC config failed: {str(e)}") from e
        return self._jwks_client

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Enforce authentication."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)
        try:
            payload = self.validate_token(
                request.headers.get("Authorization"),
                auto_error=self.should_enforce_auth(request),
            )
        except HTTPException as e:
            response = JSONResponse({"detail": e.detail}, status_code=e.status_code)
            return await response(scope, receive, send)

        # Set the payload in the request state
        setattr(
            request.state,
            self.state_key,
            payload,
        )
        return await self.app(scope, receive, send)

    def should_enforce_auth(self, request: Request) -> bool:
        """Determine if authentication should be required on a given request."""
        # If default_public, we only enforce auth if the request is for an endpoint explicitly listed as private
        if self.default_public:
            return matches_route(request, self.private_endpoints)
        # If not default_public, we enforce auth if the request is not for an endpoint explicitly listed as public
        return not matches_route(request, self.public_endpoints)

    def validate_token(
        self,
        auth_header: Annotated[str, Security(...)],
        auto_error: bool = True,
    ) -> Optional[dict[str, Any]]:
        """Dependency to validate an OIDC token."""
        if not auth_header:
            if auto_error:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authenticated",
                )
            return None

        # Extract token from header
        token_parts = auth_header.split(" ")
        if len(token_parts) != 2 or token_parts[0].lower() != "bearer":
            logger.error(f"Invalid token: {auth_header}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        [_, token] = token_parts

        # Parse & validate token
        try:
            key = self.jwks_client.get_signing_key_from_jwt(token).key
            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                # NOTE: Audience validation MUST match audience claim if set in token (https://pyjwt.readthedocs.io/en/stable/changelog.html?highlight=audience#id40)
                audience=self.allowed_jwt_audiences,
            )
        except (jwt.exceptions.InvalidTokenError, jwt.exceptions.DecodeError) as e:
            logger.exception(f"InvalidTokenError: {e=}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        return payload


class OidcFetchError(Exception):
    """Error fetching OIDC configuration."""

    ...
