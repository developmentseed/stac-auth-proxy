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

logger = getLogger(__name__)


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

        if request.method == "GET":
            cql2_filter: Optional[Expr] = getattr(request.state, self.state_key, None)
            if cql2_filter:
                scope["query_string"] = filters.append_qs_filter(
                    request.url.query, cql2_filter
                )

            initial_message = None
            body = b""

            async def validate_response(message: Message) -> None:
                nonlocal initial_message
                nonlocal body
                headers = MutableHeaders(scope=initial_message)
                if message["type"] == "http.response.start":
                    initial_message = message
                    return

                if message["type"] == "http.response.body":
                    assert initial_message, "Initial message not set"
                    assert cql2_filter, "Cql2Filter not set"

                    body += message["body"]
                    if message.get("more_body"):
                        return

                    try:
                        body = json.loads(body)
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse response body as JSON")
                        not_found_body = json.dumps({"message": "Not found"}).encode(
                            "utf-8"
                        )
                        headers["content-length"] = str(len(not_found_body))
                        initial_message["status"] = 502
                        await send(initial_message)
                        await send(
                            {
                                "type": "http.response.body",
                                "body": not_found_body,
                                "more_body": False,
                            }
                        )
                        return

                    logger.debug(
                        "Applying %s filter to %s", cql2_filter.to_text(), body
                    )
                    if cql2_filter.matches(body):
                        await send(initial_message)
                        await send(
                            {
                                "type": "http.response.body",
                                "body": json.dumps(body).encode("utf-8"),
                                "more_body": False,
                            }
                        )
                    else:
                        not_found_body = json.dumps({"message": "Not found"}).encode(
                            "utf-8"
                        )
                        headers["content-length"] = str(len(not_found_body))
                        initial_message["status"] = 404
                        await send(initial_message)
                        await send(
                            {
                                "type": "http.response.body",
                                "body": not_found_body,
                                "more_body": False,
                            }
                        )

                return message

            should_validate_response = cql2_filter and re.match(
                r"^/collections/([^/]+)/items/([^/]+)$", request.url.path
            )

            return await self.app(
                scope,
                receive,
                validate_response if should_validate_response else send,
            )

        elif request.method in ["POST", "PUT", "PATCH"]:

            async def receive_and_apply_filter() -> Message:
                message = await receive()
                if message["type"] != "http.request":
                    return message

                cql2_filter = getattr(request.state, self.state_key, None)
                if cql2_filter:
                    try:
                        body = json.loads(message.get("body", b"{}"))
                    except json.JSONDecodeError as e:
                        logger.warning("Failed to parse request body as JSON")
                        # TODO: Return a 400 error
                        raise e

                    new_body = filters.append_body_filter(body, cql2_filter)
                    message["body"] = json.dumps(new_body).encode("utf-8")
                return message

            return await self.app(
                scope,
                receive_and_apply_filter,
                send,
            )

        return await self.app(scope, receive, send)
