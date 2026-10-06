"""
Differential fuzzing: the upstream must act on the request the checks saw.

Every access-control bypass fixed so far had the same shape: auth, filters and
transaction checks decided on one view of the request (path, query params) while
the upstream acted on another. Rather than enumerate encodings, this sends random
raw paths and query strings through the proxy and asserts that any request that
reaches the upstream carries exactly the path and params the checks saw.
"""

import re
from urllib.parse import unquote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st
from utils import AppFactory

from stac_auth_proxy import Settings, configure_app
from stac_auth_proxy.utils.filters import parse_query_params

# What the filter factory (and so every path/param check) saw, per request
SEEN: list[dict] = []


class RecordingFilter:
    """A filter factory that records the request it was asked about."""

    def __init__(self, *args, **kwargs):
        """Accept the arguments the proxy passes to filter classes."""

    async def __call__(self, context: dict) -> str:
        """Record the request and allow everything."""
        SEEN.append(context["req"])
        return "true"


_RECORDING = {"cls": f"{__name__}:RecordingFilter"}

# Each segment or value is either ordinary, so that many requests reach the
# upstream, or mixed with tokens that have caused (or could cause) the checked and
# forwarded views to differ
_PLAIN = ["a", "Z", "0", "9", "-", "_", "~", ".", "collections", "items", "search"]
_SEGMENT_TOKENS = [
    *_PLAIN,
    *["Collections", "ITEMS", "bulk_items", "!$&'()*+,=:@", '"<>[]^`{|}', " "],
    *["..", "%2E", "%2e%2E", "%2F", "%252F", "%23", "%3F", "%25", "%5C", ";"],
    *["%3B", "%20", "%09", "%0A", "%00", "%C3%A9", "%FF", "%E2%80%AE", "\\"],
    *["%EF%BC%8E", "%EF%BC%8F", "e%CC%81"],  # fullwidth "." and "/", decomposed "é"
]
_QUERY_TOKENS = [
    *_PLAIN,
    *["!$'()*,:@/?[]", "%26", "%3D", "%23", "#", "+", "%2B", "%20", "%25"],
    *["%FF", "%C3%A9", "filter", "filter-lang", "false", "%5B%5D"],
]
_QUERY_KEYS = [
    *["collections", "limit", "ids", "bbox", "datetime"] * 3,
    "collections",
    "collections[]",
    "collections%5B%5D",
    "filter",
    "FILTER",
    "filter-lang",
    "filter_lang",
    "filter-crs",
    "limit",
    "ids",
    "bbox",
    "",
]


def _join(tokens, min_size=0):
    """Text made of plain tokens, or of plain and hostile ones."""
    return st.one_of(
        *(
            st.lists(st.sampled_from(t), min_size=min_size, max_size=6).map("".join)
            for t in (_PLAIN, tokens)
        )
    )


raw_paths = st.builds(
    lambda prefix, segments, slash: (
        prefix + "".join(f"/{s}" for s in segments) + ("/" if slash else "")
    ),
    st.sampled_from(["", "/collections", "/collections/c/items", "/search"]),
    st.lists(_join(_SEGMENT_TOKENS, min_size=1), max_size=4),
    st.booleans(),
).map(lambda p: p or "/")

raw_queries = st.lists(
    st.tuples(
        st.sampled_from(_QUERY_KEYS) | _join(_QUERY_TOKENS),
        _join(_QUERY_TOKENS),
        # raw (unencoded) non-ASCII bytes, as httptools passes through
        st.sampled_from([b""] * 8 + ["é".encode(), b"\xff"]),
    ),
    max_size=4,
).map(
    lambda pairs: b"&".join(k.encode() + b"=" + v.encode() + raw for k, v, raw in pairs)
)


_ORDINARY_SEGMENT = re.compile(r"[A-Za-z0-9_~-][A-Za-z0-9._~-]*|\.[A-Za-z0-9._~-]+")


def _ordinary(path: str) -> bool:
    """Whether a raw path is plain enough that it must not be rejected."""
    segments = path.strip("/").split("/")
    return path == "/" or all(
        _ORDINARY_SEGMENT.fullmatch(s) and s != ".." for s in segments
    )


def _params(query: bytes) -> list[tuple[str, str]]:
    """Params as the upstream reads them, without the proxy's filter."""
    return sorted(
        (k, v)
        for k, v in parse_query_params(query).multi_items()
        if k not in ("filter", "filter-lang")
    )


@pytest.mark.parametrize("root_path", ["", "/stac"])
def test_upstream_acts_on_what_the_checks_saw(
    mock_upstream, source_api_server, root_path
):
    """
    For random raw paths and query strings, a request either never reaches the
    upstream, or reaches it with exactly the path and query params that the
    checks (here, a filter factory matching every path) were given.
    """
    app = AppFactory(
        oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
        default_public=True,
        items_filter=_RECORDING,
        items_filter_path=".*",
        collections_filter=_RECORDING,
        collections_filter_path=".*",
    )(
        upstream_url=source_api_server,
        root_path=root_path,
        wait_for_upstream=False,
        check_conformance=False,
    )

    request_target: dict = {}

    async def uvicorn_like(scope, receive, send):
        if scope["type"] == "http":
            # The raw target, decoded once as uvicorn does
            raw_path = request_target["raw_path"]
            scope = {
                **scope,
                "raw_path": raw_path,
                "path": unquote(raw_path.decode("ascii")),
                "query_string": request_target["query_string"],
            }
        await app(scope, receive, send)

    with TestClient(uvicorn_like) as client:

        @settings(
            max_examples=400,
            deadline=None,
            suppress_health_check=[HealthCheck.function_scoped_fixture],
        )
        @given(path=raw_paths, query=raw_queries)
        def check(path, query):
            request_target["raw_path"] = f"{root_path}{path}".encode()
            request_target["query_string"] = query
            SEEN.clear()
            mock_upstream.reset_mock()

            response = client.get("/")
            assert response.status_code < 500, (path, query, response.text)
            if not mock_upstream.call_count:
                event(f"not forwarded ({response.status_code})")
                # Liveness: ordinary requests aren't rejected
                assert not (_ordinary(path) and not query), (path, response.text)
                return  # rejected, or answered by the proxy itself
            event("forwarded")

            assert mock_upstream.call_count == 1
            [seen] = SEEN
            [forwarded] = mock_upstream.call_args[0]
            forwarded_path, _, forwarded_query = (
                forwarded.url.raw_path.decode().partition("?")
            )
            assert unquote(forwarded_path) == seen["path"], (path, query)
            assert _params(forwarded_query.encode()) == sorted(
                (k, v)
                for k, v in seen["query_params"].items()
                if k not in ("filter", "filter-lang")
            ), (path, query)

        check()


@pytest.mark.parametrize("app_root_path", ["", "/stac"])
def test_app_routes_what_the_checks_saw(app_root_path):
    """
    Library mode: for random raw paths, the app's own route either isn't reached,
    or is reached with the path the checks saw (Starlette routes on scope["path"]
    minus root_path, while the checks match on request.url.path).
    """
    app = FastAPI(root_path=app_root_path)
    configure_app(
        app,
        Settings(
            upstream_url="https://stac-server",
            oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
            default_public=True,
            items_filter=_RECORDING,
            items_filter_path=".*",
            collections_filter=_RECORDING,
            collections_filter_path=".*",
        ),
    )
    routed: list[str] = []

    @app.get("/{path:path}")
    async def catch_all(path: str):
        routed.append(f"/{path}")
        return {}

    request_target: dict = {}

    async def uvicorn_like(scope, receive, send):
        if scope["type"] == "http":
            raw_path = request_target["raw_path"]
            scope = {
                **scope,
                "raw_path": raw_path,
                "path": unquote(raw_path.decode("ascii")),
                "query_string": b"",
            }
        await app(scope, receive, send)

    with TestClient(uvicorn_like) as client:

        @settings(
            max_examples=400,
            deadline=None,
            suppress_health_check=[HealthCheck.function_scoped_fixture],
        )
        @given(path=raw_paths)
        def check(path):
            request_target["raw_path"] = f"{app_root_path}{path}".encode()
            SEEN.clear()
            routed.clear()

            response = client.get("/")
            assert response.status_code < 500, (path, response.text)
            if not routed:
                event(f"not routed ({response.status_code})")
                # Liveness: ordinary requests aren't rejected
                assert not _ordinary(path), (path, response.text)
                return
            event("routed")
            [seen] = SEEN
            assert routed == [seen["path"]], path

        check()


def test_mounted_proxy_forwards_what_the_checks_saw(mock_upstream, source_api_server):
    """
    A custom proxy mounted under a sub-path: a forwarded request carries exactly
    the path the checks saw (the mount prefix included).
    """
    from starlette.applications import Starlette
    from starlette.routing import Route

    from stac_auth_proxy.handlers import ReverseProxyHandler

    app = FastAPI()
    configure_app(
        app,
        Settings(
            upstream_url=source_api_server,
            oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
            default_public=True,
            items_filter=_RECORDING,
            items_filter_path=".*",
            collections_filter=_RECORDING,
            collections_filter_path=".*",
        ),
    )
    proxy = ReverseProxyHandler(upstream=source_api_server)
    app.mount("/proxy", Starlette(routes=[Route("/{path:path}", proxy.proxy_request)]))

    request_target: dict = {}

    async def uvicorn_like(scope, receive, send):
        if scope["type"] == "http":
            raw_path = request_target["raw_path"]
            scope = {
                **scope,
                "raw_path": raw_path,
                "path": unquote(raw_path.decode("ascii")),
                "query_string": b"",
            }
        await app(scope, receive, send)

    with TestClient(uvicorn_like) as client:

        @settings(
            max_examples=200,
            deadline=None,
            suppress_health_check=[HealthCheck.function_scoped_fixture],
        )
        @given(path=raw_paths)
        def check(path):
            request_target["raw_path"] = f"/proxy{path}".encode()
            SEEN.clear()
            mock_upstream.reset_mock()

            response = client.get("/")
            assert response.status_code < 500, (path, response.text)
            if not mock_upstream.call_count:
                return
            [seen] = SEEN
            [forwarded] = mock_upstream.call_args[0]
            forwarded_path = forwarded.url.raw_path.decode().partition("?")[0]
            assert unquote(forwarded_path) == seen["path"], path

        check()
