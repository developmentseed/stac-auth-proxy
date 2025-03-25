"""Utilities for middleware response handling."""

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class JsonResponseMiddleware(ABC):
    """Base class for middleware that transforms JSON response bodies."""

    app: ASGIApp
    json_content_type_expr: str = (
        r"application/vnd\.oai\.openapi\+json;.*|application/json|application/geo\+json"
    )

    @abstractmethod
    def should_transform_response(self, request: Request) -> bool:
        """
        Determine if this request's response should be transformed.

        Args:
            request: The incoming request

        Returns
        -------
            bool: True if the response should be transformed
        """
        return request.headers.get("accept") == "application/json"

    @abstractmethod
    def transform_json(self, data: Any) -> Any:
        """
        Transform the JSON data.

        Args:
            data: The parsed JSON data

        Returns
        -------
            The transformed JSON data
        """
        pass

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process the request/response."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)
        if not self.should_transform_response(request):
            return await self.app(scope, receive, send)

        start_message: Optional[Message] = None
        body = b""
        not_json = False

        async def process_message(message: Message) -> None:
            nonlocal start_message
            nonlocal body
            nonlocal not_json
            if message["type"] == "http.response.start":
                # Delay sending start message until we've processed the body
                if not re.match(
                    self.json_content_type_expr,
                    Headers(scope=message).get("content-type", ""),
                ):
                    not_json = True
                    return await send(message)
                start_message = message
                return
            elif message["type"] != "http.response.body" or not_json:
                return await send(message)

            body += message["body"]

            # Skip body chunks until all chunks have been received
            if message.get("more_body"):
                return

            headers = MutableHeaders(scope=start_message)

            # Transform the JSON body
            if body:
                data = json.loads(body)
                transformed = self.transform_json(data)
                body = json.dumps(transformed).encode()

            # Update content-length header
            headers["content-length"] = str(len(body))
            assert start_message, "Expected start_message to be set"
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

        return await self.app(scope, receive, process_message)
