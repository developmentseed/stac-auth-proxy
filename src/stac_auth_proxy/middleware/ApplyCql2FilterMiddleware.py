"""Middleware to apply CQL2 filters."""

import json
import re
from dataclasses import dataclass
from logging import getLogger
from typing import Optional

from cql2 import Expr
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..utils import filters
from ..utils.middleware import required_conformance

logger = getLogger(__name__)


@required_conformance(
    r"http://www.opengis.net/spec/cql2/1.0/conf/basic-cql2",
    r"http://www.opengis.net/spec/cql2/1.0/conf/cql2-text",
    r"http://www.opengis.net/spec/cql2/1.0/conf/cql2-json",
    r"http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/features-filter",
    r"https://api.stacspec.org/v1\.\d+\.\d+(?:-[\w\.]+)?/item-search#filter",
)
@dataclass(frozen=True)
class ApplyCql2FilterMiddleware:
    """Middleware to apply the Cql2Filter to the request."""

    app: ASGIApp
    state_key: str = "cql2_filter"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Add the Cql2Filter to the request."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)

        cql2_filter: Optional[Expr] = getattr(request.state, self.state_key, None)

        if not cql2_filter:
            return await self.app(scope, receive, send)

        # Handle POST, PUT, PATCH
        if request.method in ["POST", "PUT", "PATCH"]:
            req_body_handler = Cql2RequestBodyAugmentor(
                app=self.app,
                cql2_filter=cql2_filter,
            )
            return await req_body_handler(scope, receive, send)

        if re.match(r"^/collections/([^/]+)/items/([^/]+)$", request.url.path):
            res_body_validator = Cql2ResponseBodyValidator(
                app=self.app,
                cql2_filter=cql2_filter,
            )
            return await res_body_validator(scope, send, receive)

        scope["query_string"] = filters.append_qs_filter(request.url.query, cql2_filter)
        return await self.app(scope, receive, send)


@dataclass(frozen=True)
class Cql2RequestBodyAugmentor:
    """Handler to augment the request body with a CQL2 filter."""

    app: ASGIApp
    cql2_filter: Expr

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Augment the request body with a CQL2 filter."""
        body = b""
        more_body = True

        # Read the body
        while more_body:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                more_body = message.get("more_body", False)

        # Modify body
        try:
            body = json.loads(body)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse request body as JSON")
            # TODO: Return a 400 error
            raise e

        # Augment the body
        assert isinstance(body, dict), "Request body must be a JSON object"
        new_body = json.dumps(
            filters.append_body_filter(body, self.cql2_filter)
        ).encode("utf-8")

        # Patch content-length in the headers
        headers = dict(scope["headers"])
        headers[b"content-length"] = str(len(new_body)).encode("latin1")
        scope["headers"] = list(headers.items())

        async def new_receive():
            return {
                "type": "http.request",
                "body": new_body,
                "more_body": False,
            }

        await self.app(scope, new_receive, send)


@dataclass
class Cql2ResponseBodyValidator:
    """Handler to validate response body with CQL2."""

    app: ASGIApp
    cql2_filter: Expr

    async def __call__(self, scope: Scope, send: Send, receive: Receive) -> None:
        """Process a response message and apply filtering if needed."""
        if scope["type"] != "http":
            return await self.app(scope, send, receive)

        body = b""
        initial_message: Optional[Message] = None

        async def _send_error_response(status: int, message: str) -> None:
            """Send an error response with the given status and message."""
            assert initial_message, "Initial message not set"
            error_body = json.dumps({"message": message}).encode("utf-8")
            headers = MutableHeaders(scope=initial_message)
            headers["content-length"] = str(len(error_body))
            initial_message["status"] = status
            await send(initial_message)
            await send(
                {
                    "type": "http.response.body",
                    "body": error_body,
                    "more_body": False,
                }
            )

        async def buffered_send(message: Message) -> None:
            """Process a response message and apply filtering if needed."""
            nonlocal body
            nonlocal initial_message

            if message["type"] == "http.response.start":
                initial_message = message
                return

            assert initial_message, "Initial message not set"

            body += message["body"]
            if message.get("more_body"):
                return

            try:
                body_json = json.loads(body)
            except json.JSONDecodeError:
                logger.warning("Failed to parse response body as JSON")
                await _send_error_response(502, "Not found")
                return

            logger.debug(
                "Applying %s filter to %s", self.cql2_filter.to_text(), body_json
            )
            if self.cql2_filter.matches(body_json):
                await send(initial_message)
                return await send(
                    {
                        "type": "http.response.body",
                        "body": json.dumps(body_json).encode("utf-8"),
                        "more_body": False,
                    }
                )
            return await _send_error_response(404, "Not found")

        return await self.app(scope, receive, buffered_send)
