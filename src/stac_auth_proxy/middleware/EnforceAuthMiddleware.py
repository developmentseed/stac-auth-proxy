"""Middleware to enforce authentication."""

import logging
from dataclasses import dataclass
from typing import Annotated, Any, Optional, Sequence
from urllib.parse import urlparse, urlunparse

import httpx
import jwt
from fastapi import HTTPException, Request, Security, status
from pydantic import HttpUrl
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ..config import EndpointMethods
from ..utils.requests import find_match

logger = logging.getLogger(__name__)


@dataclass
class EnforceAuthMiddleware:
    """Middleware to enforce authentication."""

    app: ASGIApp
    private_endpoints: EndpointMethods
    public_endpoints: EndpointMethods
    default_public: bool

    oidc_config_url: HttpUrl
    allowed_jwt_audiences: Optional[Sequence[str]] = None

    state_key: str = "payload"

    # Generated attributes
    _jwks_client: Optional[jwt.PyJWKClient] = None

    @property
    def jwks_client(self) -> jwt.PyJWKClient:
        """Get the OIDC configuration URL."""
        if not self._jwks_client:
            logger.debug("Requesting OIDC config")
            origin_url = str(self.oidc_config_url)

            try:
                response = httpx.get(origin_url)
                response.raise_for_status()
                oidc_config = response.json()

                # NOTE: We manually replace the origin of the jwks_uri in the event that
                # the jwks_uri is not available from within the proxy.
                oidc_url = urlparse(origin_url)
                jwks_uri = urlunparse(
                    urlparse(oidc_config["jwks_uri"])._replace(
                        netloc=oidc_url.netloc, scheme=oidc_url.scheme
                    )
                )
                if jwks_uri != oidc_config["jwks_uri"]:
                    logger.warning(
                        "JWKS URI has been rewritten from %s to %s",
                        oidc_config["jwks_uri"],
                        jwks_uri,
                    )
                self._jwks_client = jwt.PyJWKClient(jwks_uri)
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
        match = find_match(
            request.url.path,
            request.method,
            private_endpoints=self.private_endpoints,
            public_endpoints=self.public_endpoints,
            default_public=self.default_public,
        )
        try:
            payload = self.validate_token(
                request.headers.get("Authorization"),
                auto_error=match.is_private,
                required_scopes=match.required_scopes,
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

    def validate_token(
        self,
        auth_header: Annotated[str, Security(...)],
        auto_error: bool = True,
        required_scopes: Optional[Sequence[str]] = None,
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

        if required_scopes:
            for scope in required_scopes:
                if scope not in payload["scope"].split(" "):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Not enough permissions",
                        headers={"WWW-Authenticate": f'Bearer scope="{scope}"'},
                    )
        return payload


class OidcFetchError(Exception):
    """Error fetching OIDC configuration."""

    ...
