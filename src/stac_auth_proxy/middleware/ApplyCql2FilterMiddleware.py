"""Middleware to apply CQL2 filters."""

import json
import re
from dataclasses import dataclass, field
from functools import partial
from logging import getLogger
from typing import Callable, Optional

from cql2 import Expr
from starlette.datastructures import MutableHeaders, State
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

        get_cql2_filter: Callable[[], Optional[Expr]] = partial(
            getattr, request.state, self.state_key, None
        )

        # Handle POST, PUT, PATCH
        if request.method in ["POST", "PUT", "PATCH"]:
            return await self.app(
                scope,
                Cql2RequestBodyAugmentor(
                    receive=receive,
                    state=request.state,
                    get_cql2_filter=get_cql2_filter,
                ),
                send,
            )

        cql2_filter = get_cql2_filter()
        if not cql2_filter:
            return await self.app(scope, receive, send)

        if re.match(r"^/collections/([^/]+)/items/([^/]+)$", request.url.path):
            return await self.app(
                scope,
                receive,
                Cql2ResponseBodyValidator(cql2_filter=cql2_filter, send=send),
            )

        scope["query_string"] = filters.append_qs_filter(request.url.query, cql2_filter)
        return await self.app(scope, receive, send)


@dataclass(frozen=True)
class Cql2RequestBodyAugmentor:
    """Handler to augment the request body with a CQL2 filter."""

    receive: Receive
    state: State
    get_cql2_filter: Callable[[], Optional[Expr]]

    async def __call__(self) -> Message:
        """Process a request body and augment with a CQL2 filter if available."""
        message = await self.receive()
        if message["type"] != "http.request":
            return message

        # NOTE: Can only get cql2 filter _after_ calling self.receive()
        cql2_filter = self.get_cql2_filter()
        if not cql2_filter:
            return message

        try:
            body = json.loads(message.get("body", b"{}"))
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse request body as JSON")
            # TODO: Return a 400 error
            raise e

        new_body = filters.append_body_filter(body, cql2_filter)
        message["body"] = json.dumps(new_body).encode("utf-8")
        return message


@dataclass
class Cql2ResponseBodyValidator:
    """Handler to validate response body with CQL2."""

    send: Send
    cql2_filter: Expr
    initial_message: Optional[Message] = field(init=False)
    body: bytes = field(init=False, default_factory=bytes)

    async def __call__(self, message: Message) -> None:
        """Process a response message and apply filtering if needed."""
        if message["type"] == "http.response.start":
            self.initial_message = message
            return

        if message["type"] == "http.response.body":
            assert self.initial_message, "Initial message not set"

            self.body += message["body"]
            if message.get("more_body"):
                return

            try:
                body_json = json.loads(self.body)
            except json.JSONDecodeError:
                logger.warning("Failed to parse response body as JSON")
                await self._send_error_response(502, "Not found")
                return

            logger.debug(
                "Applying %s filter to %s", self.cql2_filter.to_text(), body_json
            )
            if self.cql2_filter.matches(body_json):
                await self.send(self.initial_message)
                return await self.send(
                    {
                        "type": "http.response.body",
                        "body": json.dumps(body_json).encode("utf-8"),
                        "more_body": False,
                    }
                )
            return await self._send_error_response(404, "Not found")

    async def _send_error_response(self, status: int, message: str) -> None:
        """Send an error response with the given status and message."""
        assert self.initial_message, "Initial message not set"
        error_body = json.dumps({"message": message}).encode("utf-8")
        headers = MutableHeaders(scope=self.initial_message)
        headers["content-length"] = str(len(error_body))
        self.initial_message["status"] = status
        await self.send(self.initial_message)
        await self.send(
            {
                "type": "http.response.body",
                "body": error_body,
                "more_body": False,
            }
        )
