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
)
@dataclass(frozen=True)
class ApplyCql2FilterMiddleware:
    """Middleware to apply the Cql2Filter to the request."""

    app: ASGIApp
    state_key: str = "cql2_filter"

    single_record_endpoints = [
        r"^/collections/([^/]+)/items/([^/]+)$",
        r"^/collections/([^/]+)$",
    ]

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

        # Handle single record requests (ie non-filterable endpoints)
        if any(
            re.match(expr, request.url.path) for expr in self.single_record_endpoints
        ):
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

        async def _send_error_response(status: int, code: str, message: str) -> None:
            """Send an error response with the given status and message."""
            assert initial_message, "Initial message not set"
            response_dict = {
                "code": code,
                "description": message,
            }
            response_bytes = json.dumps(response_dict).encode("utf-8")
            headers = MutableHeaders(scope=initial_message)
            headers["content-length"] = str(len(response_bytes))
            initial_message["status"] = status
            await send(initial_message)
            await send(
                {
                    "type": "http.response.body",
                    "body": response_bytes,
                    "more_body": False,
                }
            )

        async def buffered_send(message: Message) -> None:
            """Process a response message and apply filtering if needed."""
            nonlocal body
            nonlocal initial_message
            initial_message = initial_message or message
            # NOTE: to avoid data-leak, we process 404s so their responses are the same as rejected 200s
            should_process = initial_message["status"] in [200, 404]

            if not should_process:
                return await send(message)

            if message["type"] == "http.response.start":
                # Hold off on sending response headers until we've validated the response body
                return

            body += message["body"]
            if message.get("more_body"):
                return

            try:
                body_json = json.loads(body)
            except json.JSONDecodeError:
                msg = "Failed to parse response body as JSON"
                logger.warning(msg)
                await _send_error_response(status=502, code="ParseError", message=msg)
                return

            try:
                cql2_matches = self.cql2_filter.matches(body_json)
            except Exception as e:
                cql2_matches = False
                logger.warning("Failed to apply filter: %s", e)

            if cql2_matches:
                logger.debug("Response matches filter, returning record")
                await send(initial_message)
                return await send(
                    {
                        "type": "http.response.body",
                        "body": json.dumps(body_json).encode("utf-8"),
                        "more_body": False,
                    }
                )
            logger.debug("Response did not match filter, returning 404")
            return await _send_error_response(
                status=404, code="NotFoundError", message="Record not found."
            )

        return await self.app(scope, receive, buffered_send)
