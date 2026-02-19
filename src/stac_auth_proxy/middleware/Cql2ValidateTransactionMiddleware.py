"""Middleware to validate transaction requests against a CQL2 filter."""

import json
import re
from dataclasses import dataclass, field
from logging import getLogger
from typing import Optional

import httpx
from cql2 import Expr
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ..utils.middleware import required_conformance

logger = getLogger(__name__)


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
    upstream_url: str
    state_key: str = "cql2_filter"

    _client: httpx.AsyncClient = field(init=False)

    # Transaction endpoint patterns
    item_create_pattern = r"^/collections/([^/]+)/items$"
    item_modify_pattern = r"^/collections/([^/]+)/items/([^/]+)$"
    collection_create_pattern = r"^/collections$"
    collection_modify_pattern = r"^/collections/([^/]+)$"

    def __post_init__(self):
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(base_url=self.upstream_url)

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

        # Determine operation type
        if method == "POST" and (
            re.match(self.item_create_pattern, path)
            or re.match(self.collection_create_pattern, path)
        ):
            return await self._handle_create(scope, receive, send, cql2_filter)

        if method in ("PUT", "PATCH") and (
            re.match(self.item_modify_pattern, path)
            or re.match(self.collection_modify_pattern, path)
        ):
            return await self._handle_update(
                scope, receive, send, cql2_filter, path, method
            )

        if method == "DELETE" and (
            re.match(self.item_modify_pattern, path)
            or re.match(self.collection_modify_pattern, path)
        ):
            return await self._handle_delete(scope, receive, send, cql2_filter, path)

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

    async def _fetch_existing(self, path: str) -> Optional[dict]:
        """Fetch the existing record from upstream."""
        response = await self._client.get(path)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

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

    async def _handle_update(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        cql2_filter: Expr,
        path: str,
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
            existing = await self._fetch_existing(path)
        except httpx.HTTPError:
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
            response = JSONResponse(
                {"code": "NotFoundError", "description": "Record not found."},
                status_code=404,
            )
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
        path: str,
    ) -> None:
        """Validate delete requests."""
        try:
            existing = await self._fetch_existing(path)
        except httpx.HTTPError:
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
            response = JSONResponse(
                {"code": "NotFoundError", "description": "Record not found."},
                status_code=404,
            )
            return await response(scope, receive, send)

        await self.app(scope, receive, send)
