"""Middleware to remove ROOT_PATH from incoming requests and update links in responses."""

import logging
from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from ..config import EndpointMethods
from ..utils.requests import find_match

logger = logging.getLogger(__name__)


@dataclass
class AuthOptionsMiddleware:
    """Middleware to enform client of users capabilities in response to OPTIONS request."""

    app: ASGIApp
    private_endpoints: EndpointMethods
    public_endpoints: EndpointMethods
    default_public: bool
    state_key: str = "payload"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Check capabilities of the user."""
        print("HERE")
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        if scope["method"] != "OPTIONS":
            return await self.app(scope, receive, send)

        # Get endpoint requirements
        methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
        method_requirements = {}
        for method in methods:
            match = find_match(
                path=scope["path"],
                method=method,
                private_endpoints=self.private_endpoints,
                public_endpoints=self.public_endpoints,
                default_public=self.default_public,
            )
            method_requirements[method] = match

        # Get user (maybe)
        request = Request(scope)
        assert hasattr(
            request.state, self.state_key
        ), "Auth Payload not set in request state. Is state_key set correctly? Does the EnforceAuthMiddleware run before this middleware?"
        user = getattr(request.state, self.state_key, None)
        user_scopes = user.get("scope", "").split(" ") if user else []

        # Get user capabilities
        valid_methods = []
        for method, match in method_requirements.items():
            # Is public
            if not match.is_private:
                valid_methods.append(method)
                continue

            # Is private and user has all required scopes
            if user and all(scope in user_scopes for scope in match.required_scopes):
                valid_methods.append(method)
                continue

        # Construct response
        headers = {
            "Allow": ", ".join(valid_methods),
            "Access-Control-Allow-Methods": ", ".join(valid_methods),
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Max-Age": "86400",  # 24 hours
        }

        # Add CORS origin if provided in request
        origin = request.headers.get("Origin")
        if origin:
            headers["Access-Control-Allow-Origin"] = origin

        response = Response(
            content="",
            status_code=204,
            headers=headers,
        )
        return await response(scope, receive, send)
