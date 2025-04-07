"""Utilities for middleware response handling."""

import json
from abc import ABC, abstractmethod
from typing import Any, Optional

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class JsonResponseMiddleware(ABC):
    """Base class for middleware that transforms JSON response bodies."""

    app: ASGIApp

    @abstractmethod
    def should_transform_response(
        self, request: Request, scope: Scope
    ) -> bool:  # mypy: ignore
        """
        Determine if this response should be transformed. At a minimum, this
        should check the request's path and content type.

        Returns
        -------
            bool: True if the response should be transformed
        """
        ...

    @abstractmethod
    def transform_json(self, data: Any, request: Request) -> Any:
        """
        Transform the JSON data.

        Args:
            data: The parsed JSON data

        Returns
        -------
            The transformed JSON data
        """
        ...

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process the request/response."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        start_message: Optional[Message] = None
        body = b""

        async def transform_response(message: Message) -> None:
            nonlocal start_message
            nonlocal body

            start_message = start_message or message
            headers = MutableHeaders(scope=start_message)
            request = Request(scope)

            if not self.should_transform_response(
                request=request,
                scope=start_message,
            ):
                # For non-JSON responses, send the start message immediately
                await send(message)
                return

            # Delay sending start message until we've processed the body
            if message["type"] == "http.response.start":
                return

            body += message["body"]

            # Skip body chunks until all chunks have been received
            if message.get("more_body"):
                return

            # Transform the JSON body
            if body:
                data = json.loads(body)
                transformed = self.transform_json(data, request=request)
                body = json.dumps(transformed).encode()

            # Update content-length header
            headers["content-length"] = str(len(body))
            start_message["headers"] = [
                (key.encode(), value.encode()) for key, value in headers.items()
            ]

            # Send response
            await send(start_message)
            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                    "more_body": False,
                }
            )

        return await self.app(scope, receive, transform_response)


def required_conformance(
    *conformances: str,
    attr_name: str = "__required_conformances__",
):
    """Register required conformance classes with a middleware class."""

    def decorator(middleware):
        setattr(middleware, attr_name, list(conformances))
        return middleware

    return decorator
