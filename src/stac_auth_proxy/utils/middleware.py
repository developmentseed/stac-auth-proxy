"""Utilities for middleware response handling."""

import gzip
import json
import zlib
from abc import ABC, abstractmethod
from typing import Any, Optional

import brotli
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ENCODING_HANDLERS = {
    "gzip": gzip,
    "deflate": zlib,
    "br": brotli,
}


class JsonResponseMiddleware(ABC):
    """Base class for middleware that transforms JSON response bodies."""

    app: ASGIApp

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
        pass

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

        async def process_message(message: Message) -> None:
            nonlocal start_message
            nonlocal body

            if message["type"] == "http.response.start":
                # Delay sending start message until we've processed the body
                start_message = message
                return
            elif message["type"] != "http.response.body":
                return await send(message)

            body += message["body"]

            # Skip body chunks until all chunks have been received
            if message["more_body"]:
                return

            # Handle compression/decompression
            headers = MutableHeaders(scope=start_message)
            content_encoding = headers.get("content-encoding", "").lower()
            handler = None
            if content_encoding:
                handler = ENCODING_HANDLERS.get(content_encoding)
                assert handler, f"Unsupported content encoding: {content_encoding}"
                body = (
                    handler.decompress(body)
                    if content_encoding != "deflate"
                    else handler.decompress(body, -zlib.MAX_WBITS)
                )

            # Transform the JSON body
            data = json.loads(body)
            transformed = self.transform_json(data)
            body = json.dumps(transformed).encode()

            # Re-compress if necessary
            if handler:
                body = handler.compress(body)

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
