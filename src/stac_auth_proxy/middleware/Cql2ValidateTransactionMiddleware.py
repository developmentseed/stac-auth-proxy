"""Middleware to validate transaction requests against a CQL2 filter."""

import json
from dataclasses import dataclass
from logging import getLogger
from typing import Optional

from cql2 import Expr
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ..utils.middleware import required_conformance
from ..utils.requests import match_path

logger = getLogger(__name__)


class UpstreamError(Exception):
    """Raised when the existing record could not be fetched."""


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Non-dict values from override replace base."""
    result = {**base}
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@required_conformance(
    r"http://www.opengis.net/spec/cql2/1.0/conf/basic-cql2",
    r"http://www.opengis.net/spec/cql2/1.0/conf/cql2-text",
    r"http://www.opengis.net/spec/cql2/1.0/conf/cql2-json",
)
@dataclass
class Cql2ValidateTransactionMiddleware:
    """Middleware to validate transaction requests against a CQL2 filter."""

    app: ASGIApp
    state_key: str = "cql2_filter"
    read_state_key: str = "cql2_read_filter"

    # Transaction endpoint patterns
    items_pattern = r"^/collections/([^/]+)/(items|bulk_items)(?:/([^/]+))?$"
    collections_pattern = r"^/collections(?:/([^/]+))?$"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Validate transaction requests against the CQL2 filter."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)
        cql2_filter: Optional[Expr] = getattr(request.state, self.state_key, None)
        if not cql2_filter:
            return await self.app(scope, receive, send)

        path = request.url.path
        method = request.method

        # Match items endpoints: /collections/{id}/items, /collections/{id}/bulk_items, /collections/{id}/items/{id}
        if match := match_path(self.items_pattern, path):
            if method == "POST":
                if match.group(2).lower() == "bulk_items":
                    return await self._handle_bulk_create(
                        scope, receive, send, cql2_filter
                    )
                return await self._handle_create(scope, receive, send, cql2_filter)
            if method in ("PUT", "PATCH"):
                return await self._handle_update(
                    scope, receive, send, cql2_filter, method
                )
            if method == "DELETE":
                return await self._handle_delete(scope, receive, send, cql2_filter)

        # Match collections endpoints: /collections, /collections/{id}
        if match_path(self.collections_pattern, path):
            if method == "POST":
                return await self._handle_create(scope, receive, send, cql2_filter)
            if method in ("PUT", "PATCH"):
                return await self._handle_update(
                    scope, receive, send, cql2_filter, method
                )
            if method == "DELETE":
                return await self._handle_delete(scope, receive, send, cql2_filter)

        # Not a transaction endpoint, pass through
        return await self.app(scope, receive, send)

    async def _read_body(self, receive: Receive) -> bytes:
        """Read the full request body."""
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                more_body = message.get("more_body", False)
        return body

    def _make_receive(self, body: bytes) -> Receive:
        """Create a new receive callable that returns the given body."""

        async def new_receive():
            return {
                "type": "http.request",
                "body": body,
                "more_body": False,
            }

        return new_receive

    async def _fetch_existing(self, scope: Scope) -> Optional[dict]:
        """
        Fetch the existing record by sending a GET for the same path to the
        downstream app, in-process.

        When deployed as a proxy, this reaches the upstream via the reverse proxy
        handler; when deployed as middleware, it reaches the STAC API's routes
        directly. Either way the request never re-enters the auth middleware, so no
        credentials need to be forwarded.

        The GET carries the caller's read filter, when there is one, in place of the
        write filter, so a downstream response check returns a record the caller may
        read and the write check can refuse it with 403 rather than 404.
        """
        state = dict(scope.get("state", {}))
        read_filter = state.get(self.read_state_key)
        if read_filter is not None:
            state[self.state_key] = read_filter
        sub_scope = {
            **scope,
            "method": "GET",
            "query_string": b"",
            # Drop the caller's headers (body sizing, conditionals, encodings) so the
            # downstream always answers with a complete, plain JSON body.
            "headers": [(k, v) for k, v in scope["headers"] if k == b"host"]
            + [(b"accept", b"application/json")],
            # Copy so downstream writes to request.state can't leak into the caller's
            # request.
            "state": state,
        }
        status = None
        body = b""

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            nonlocal status, body
            if message["type"] == "http.response.start":
                status = message["status"]
            else:
                body += message.get("body", b"")

        try:
            await self.app(sub_scope, receive, send)
        except Exception as e:
            raise UpstreamError("Failed to fetch existing record") from e

        if status == 404:
            return None
        if status != 200:
            raise UpstreamError(f"Unexpected status {status} fetching existing record")
        try:
            return json.loads(body)
        except json.JSONDecodeError as e:
            raise UpstreamError("Existing record is not valid JSON") from e

    def _denied_existing(self, scope: Scope, existing: dict) -> JSONResponse:
        """
        Refuse a change to an existing record that the filter does not match.

        A record the caller may read is refused with 403; any other record is
        reported as not found, so its existence is not disclosed.
        """
        read_filter: Optional[Expr] = getattr(
            Request(scope).state, self.read_state_key, None
        )
        if read_filter is not None and self._readable(read_filter, existing):
            return JSONResponse(
                {
                    "code": "ForbiddenError",
                    "description": "Resource does not match access filter.",
                },
                status_code=403,
            )
        return JSONResponse(
            {"code": "NotFoundError", "description": "Record not found."},
            status_code=404,
        )

    @staticmethod
    def _readable(read_filter: Expr, record: dict) -> bool:
        """Check the read filter against a record; an evaluation error counts as no match."""
        try:
            return bool(read_filter.matches(record))
        except Exception as e:
            logger.warning("Could not evaluate the read filter on a record: %s", e)
            return False

    async def _handle_create(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        cql2_filter: Expr,
    ) -> None:
        """Validate create requests."""
        body = await self._read_body(receive)

        try:
            body_json = json.loads(body) if body else {}
        except json.JSONDecodeError:
            response = JSONResponse(
                {
                    "code": "ParseError",
                    "description": "Request body must be valid JSON.",
                },
                status_code=400,
            )
            return await response(scope, receive, send)

        if not cql2_filter.matches(body_json):
            response = JSONResponse(
                {
                    "code": "ForbiddenError",
                    "description": "Resource does not match access filter.",
                },
                status_code=403,
            )
            return await response(scope, receive, send)

        # Reconstruct receive and forward
        scope = dict(scope)
        await self.app(scope, self._make_receive(body), send)

    async def _handle_bulk_create(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        cql2_filter: Expr,
    ) -> None:
        """Validate bulk item create requests."""
        body = await self._read_body(receive)

        try:
            body_json = json.loads(body) if body else {}
        except json.JSONDecodeError:
            response = JSONResponse(
                {
                    "code": "ParseError",
                    "description": "Request body must be valid JSON.",
                },
                status_code=400,
            )
            return await response(scope, receive, send)

        items = body_json.get("items", {})
        if not isinstance(items, dict):
            response = JSONResponse(
                {
                    "code": "ParseError",
                    "description": "Bulk items body must contain an 'items' object.",
                },
                status_code=400,
            )
            return await response(scope, receive, send)

        failed = [
            item_id for item_id, item in items.items() if not cql2_filter.matches(item)
        ]

        if failed:
            response = JSONResponse(
                {
                    "code": "ForbiddenError",
                    "description": f"Items do not match access filter: {', '.join(failed)}",
                },
                status_code=403,
            )
            return await response(scope, receive, send)

        # Reconstruct receive and forward
        scope = dict(scope)
        await self.app(scope, self._make_receive(body), send)

    async def _handle_update(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        cql2_filter: Expr,
        method: str,
    ) -> None:
        """Validate update requests."""
        body = await self._read_body(receive)

        try:
            body_json = json.loads(body) if body else {}
        except json.JSONDecodeError:
            response = JSONResponse(
                {
                    "code": "ParseError",
                    "description": "Request body must be valid JSON.",
                },
                status_code=400,
            )
            return await response(scope, receive, send)

        # Fetch existing record
        try:
            existing = await self._fetch_existing(scope)
        except UpstreamError:
            response = JSONResponse(
                {
                    "code": "UpstreamError",
                    "description": "Failed to fetch record from upstream.",
                },
                status_code=502,
            )
            return await response(scope, receive, send)

        if existing is None:
            response = JSONResponse(
                {"code": "NotFoundError", "description": "Record not found."},
                status_code=404,
            )
            return await response(scope, receive, send)

        # Validate existing record matches filter
        if not cql2_filter.matches(existing):
            response = self._denied_existing(scope, existing)
            return await response(scope, receive, send)

        # Merge for validation
        if method == "PATCH":
            merged = _deep_merge(existing, body_json)
        else:
            merged = body_json

        # Validate merged result matches filter
        if not cql2_filter.matches(merged):
            response = JSONResponse(
                {
                    "code": "ForbiddenError",
                    "description": "Updated resource does not match access filter.",
                },
                status_code=403,
            )
            return await response(scope, receive, send)

        # Forward
        scope = dict(scope)
        await self.app(scope, self._make_receive(body), send)

    async def _handle_delete(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        cql2_filter: Expr,
    ) -> None:
        """Validate delete requests."""
        try:
            existing = await self._fetch_existing(scope)
        except UpstreamError:
            response = JSONResponse(
                {
                    "code": "UpstreamError",
                    "description": "Failed to fetch record from upstream.",
                },
                status_code=502,
            )
            return await response(scope, receive, send)

        if existing is None:
            response = JSONResponse(
                {"code": "NotFoundError", "description": "Record not found."},
                status_code=404,
            )
            return await response(scope, receive, send)

        if not cql2_filter.matches(existing):
            response = self._denied_existing(scope, existing)
            return await response(scope, receive, send)

        await self.app(scope, receive, send)
