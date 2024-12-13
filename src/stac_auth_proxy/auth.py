"""OIDC authentication module for validating JWTs."""

import json
import logging
import urllib.request
from dataclasses import dataclass, field
from typing import Annotated, Any, Callable, Optional, Sequence

import jwt
from fastapi import HTTPException, Security, security, status
from fastapi.security.base import SecurityBase
from pydantic import HttpUrl

logger = logging.getLogger(__name__)


@dataclass
class OpenIdConnectAuth:
    """OIDC authentication class to generate auth handlers."""

    openid_configuration_url: HttpUrl
    openid_configuration_internal_url: Optional[HttpUrl] = None
    allowed_jwt_audiences: Optional[Sequence[str]] = None

    # Generated attributes
    auth_scheme: SecurityBase = field(init=False)
    jwks_client: jwt.PyJWKClient = field(init=False)
    validated_user: Callable[..., Any] = field(init=False)
    maybe_validated_user: Callable[..., Any] = field(init=False)

    def __post_init__(self):
        """Initialize the OIDC authentication class."""
        logger.debug("Requesting OIDC config")
        origin_url = str(
            self.openid_configuration_internal_url or self.openid_configuration_url
        )
        with urllib.request.urlopen(origin_url) as response:
            if response.status != 200:
                logger.error(
                    "Received a non-200 response when fetching OIDC config: %s",
                    response.text,
                )
                raise OidcFetchError(
                    f"Request for OIDC config failed with status {response.status}"
                )
            oidc_config = json.load(response)
            self.jwks_client = jwt.PyJWKClient(oidc_config["jwks_uri"])

        self.auth_scheme = security.OpenIdConnect(
            openIdConnectUrl=str(self.openid_configuration_url),
            auto_error=False,
        )
        self.validated_user = self._build(auto_error=True)
        self.maybe_validated_user = self._build(auto_error=False)

    def _build(self, auto_error: bool = True):
        """Build a dependency for validating an OIDC token."""

        def valid_token_dependency(
            auth_header: Annotated[str, Security(self.auth_scheme)],
            required_scopes: security.SecurityScopes,
        ):
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

            # Validate scopes (if required)
            for scope in required_scopes.scopes:
                if scope not in payload["scope"]:
                    if auto_error:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not enough permissions",
                            headers={
                                "WWW-Authenticate": f'Bearer scope="{required_scopes.scope_str}"'
                            },
                        )
                    return None

            return payload

        return valid_token_dependency


class OidcFetchError(Exception):
    """Error fetching OIDC configuration."""

    pass
