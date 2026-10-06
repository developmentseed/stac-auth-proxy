"""Test rejection of request paths that are interpreted differently downstream."""

from urllib.parse import unquote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from utils import AppFactory

from stac_auth_proxy import Settings, configure_app
from stac_auth_proxy.handlers import ReverseProxyHandler

OIDC_DISCOVERY_URL = "https://example-stac-api.com/.well-known/openid-configuration"

app_factory = AppFactory(
    oidc_discovery_url=OIDC_DISCOVERY_URL,
    default_public=True,
    items_filter={
        "cls": "stac_auth_proxy.filters:Template",
        "args": ["collection = 'allowed'"],
    },
    collections_filter={
        "cls": "stac_auth_proxy.filters:Template",
        "args": ["id = 'allowed'"],
    },
)


def _client(app, **scope_overrides) -> TestClient:
    """
    TestClient for the app, decoding the path once as uvicorn does.

    Starlette's TestClient decodes the path twice ("%252F" -> "/"), which would
    hide double-encoding issues. ``scope_overrides`` replace other scope fields,
    as an ASGI adapter (e.g. Mangum) or outer middleware might.
    """

    async def uvicorn_like(scope, receive, send):
        if scope["type"] == "http":
            scope = {
                **scope,
                "path": unquote(scope["raw_path"].decode("ascii")),
                **scope_overrides,
            }
        await app(scope, receive, send)

    return TestClient(uvicorn_like)


def _proxy_client(upstream_url: str, **scope_overrides) -> TestClient:
    return _client(app_factory(upstream_url=upstream_url), **scope_overrides)


def _forwarded_path(mock_upstream, sent: str) -> str:
    """Path the upstream sees, once it decodes the forwarded raw path."""
    assert mock_upstream.call_count == 1, (sent, mock_upstream.call_count)
    [request] = mock_upstream.call_args[0]
    return unquote(request.url.raw_path.decode().partition("?")[0])


@pytest.mark.parametrize(
    "method, path",
    [
        # "#" / "?" truncate request.url.path, dropping or overriding the filter
        ("GET", "/search%23"),
        ("GET", "/search%3Ffilter%3Did%20IS%20NOT%20NULL%26x%3D"),
        ("GET", "/collections/c/items%23"),
        ("GET", "/collections%23"),
        ("DELETE", "/collections/c/items/a%3Fb"),
        # "%" is decoded a second time upstream, skipping path-based checks
        ("GET", "/collections%252Fc"),
        ("GET", "/collections/c/items%252Fx"),
        ("DELETE", "/collections%252Fd"),
        # dot segments are collapsed by httpx, skipping path-based checks
        ("DELETE", "/collections/c/items/..%2F..%2Fd"),
        ("GET", "/x/..%2Fsearch"),
        ("GET", "/collections/c/items/.%2Fx"),
        # empty segments
        ("GET", "/collections//"),
        ("GET", "/collections//c"),
        # "\" is treated as "/" by some upstreams
        ("GET", "/collections/c/items/a%5Cb"),
    ],
)
def test_ambiguous_paths_rejected(mock_upstream, source_api_server, method, path):
    """
    Ambiguous paths never reach the upstream. They get a 400, unless auth (401) or
    a response filter (404) answers first.
    """
    response = _proxy_client(source_api_server).request(method, path)
    assert response.status_code in (400, 401, 404)
    assert mock_upstream.call_count == 0


@pytest.mark.parametrize(
    "template", ["/search{}", "/collections/c/items/a{}b", "/collections{}d"]
)
def test_every_encoded_byte_rejected_or_forwarded_as_addressed(
    mock_upstream, source_api_server, template
):
    """
    Exhaustive check over every single- and double-percent-encoded byte: a path is
    either rejected, or the upstream receives exactly the path the client addressed
    (so the path-based checks ran on the same path the upstream acts on).
    """
    # No filters: they don't change the forwarded path, and validating them is slow
    app = AppFactory(oidc_discovery_url=OIDC_DISCOVERY_URL, default_public=True)(
        upstream_url=source_api_server,
        wait_for_upstream=False,
        check_conformance=False,
    )
    with _client(app) as client:
        for byte in range(256):
            for encoded in (f"%{byte:02X}", f"%25{byte:02X}"):
                sent = template.format(encoded)
                mock_upstream.reset_mock()
                if client.get(sent).status_code == 400:
                    assert mock_upstream.call_count == 0, sent
                    continue
                assert _forwarded_path(mock_upstream, sent) == unquote(sent), sent


@pytest.mark.parametrize(
    "method, path, forwarded",
    [
        ("GET", "/search/", "/search/"),
        ("GET", "/search%2F", "/search/"),
        ("GET", "/collections/c/", "/collections/c/"),
    ],
)
def test_trailing_slash_forwarded_and_filtered(
    mock_upstream, source_api_server, method, path, forwarded
):
    """
    A trailing slash reaches the upstream as sent, while path rules match "/x/" as
    "/x" (many upstreams ignore the slash), so e.g. the "/search" filter applies.
    """
    _proxy_client(source_api_server).request(method, path)
    assert _forwarded_path(mock_upstream, path) == forwarded
    [request] = mock_upstream.call_args[0]
    if forwarded == "/search/":
        assert "filter" in request.url.params


@pytest.mark.parametrize(
    "method, path", [("DELETE", "/collections/c/items/i/"), ("POST", "/collections/")]
)
def test_trailing_slash_cannot_skip_auth(
    mock_upstream, source_api_server, method, path
):
    """A trailing slash doesn't skip "$"-anchored private endpoints."""
    response = _proxy_client(source_api_server).request(method, path)
    assert response.status_code == 401
    assert mock_upstream.call_count == 0


@pytest.mark.parametrize("host", [b"my_svc:80", None])
def test_no_server_and_unparseable_host_proxied(mock_upstream, source_api_server, host):
    """A unix socket (no server) with a Host Starlette can't parse, or none, is fine."""
    headers = [(b"host", host)] if host else []
    client = _proxy_client(source_api_server, server=None, headers=headers)
    assert client.get("/search").status_code == 200
    assert _forwarded_path(mock_upstream, "/search") == "/search"


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/search",
        "/collections/c/items/v1.2",
        "/collections/c/items/..x",
        # printable ASCII with no special meaning once decoded
        *(f"/collections/c/items/a{c}b" for c in '"<>[]^`{|}'),
        "/collections/c/items/a%7Cb",
        "/collections/c/items/a%5Bb%5D",
        "/collections/c/items/a%7Bb%7D",
        # re-encoded by httpx and decoded back to the same value upstream
        "/collections/c/items/scene%20001",
        "/collections/c/items/caf%C3%A9-1",
    ],
)
def test_unambiguous_paths_proxied(mock_upstream, source_api_server, path):
    """Unambiguous paths reach the upstream exactly as addressed."""
    _proxy_client(source_api_server).get(path)
    assert _forwarded_path(mock_upstream, path) == unquote(path)


@pytest.mark.parametrize(
    "method, path, scope_overrides",
    [
        # Mangum takes the scheme from X-Forwarded-Proto ...
        ("DELETE", "/", {"scheme": "https://x/collections%2Fd#"}),
        ("GET", "/", {"scheme": "https://x/healthz/../collections/c/items#"}),
        # ... and the server from the Host header, which Starlette then uses as the
        # URL's host since it doesn't look like one
        (
            "DELETE",
            "/",
            {"server": ("x/collections%2Fd#", 443), "headers": [(b"host", b"x/c#")]},
        ),
        # an unknown scheme without a usable Host header makes Starlette raise
        ("GET", "/search", {"scheme": "x", "headers": [(b"host", b"x/")]}),
    ],
)
def test_url_divergence_rejected(
    mock_upstream, source_api_server, method, path, scope_overrides
):
    """
    Auth, filters and the proxy use request.url.path, which Starlette rebuilds from
    the scheme and server too, so those must not change the path either.
    """
    response = _proxy_client(source_api_server, **scope_overrides).request(method, path)
    assert response.status_code == 400
    assert mock_upstream.call_count == 0


def _library_app(**settings) -> FastAPI:
    """Non-proxy mode: the app serves its own routes behind the middleware."""
    app = FastAPI()
    configure_app(
        app,
        Settings(
            upstream_url="https://stac-server",
            oidc_discovery_url=OIDC_DISCOVERY_URL,
            **settings,
        ),
    )

    @app.get("/collections/{collection_id}/items/{item_id}")
    def get_item(collection_id: str, item_id: str):
        return {"collection": collection_id, "id": item_id}

    return app


@pytest.mark.parametrize(
    "path, item_id",
    [
        ("/collections/c/items/my%20item", "my item"),
        ("/collections/c/items/caf%C3%A9", "café"),
        ("/collections/c/items/50%25-cloud", "50%-cloud"),
        ("/collections/c/items/a;b", "a;b"),
        ("/collections/c/items/a%5Cb", "a\\b"),
    ],
)
def test_library_mode_serves_own_routes(path, item_id):
    """Without forwarding, only paths that request.url.path would change are rejected."""
    response = _client(_library_app(default_public=True)).get(path)
    assert response.status_code == 200, response.text
    assert response.json()["id"] == item_id


@pytest.mark.parametrize(
    "path, scope_overrides",
    [
        ("/collections/c/items/a%23b", {}),
        ("/collections/c/items/a%3Fb", {}),
        ("/collections/c/items/a%09b", {}),
        # e.g. stac-fastapi's ProxyHeaderMiddleware copying X-Forwarded-Proto
        ("/collections/private/items/secret", {"scheme": "http://x/#"}),
    ],
)
def test_library_mode_rejects_url_divergence(path, scope_overrides):
    """Paths whose request.url.path differs from the routed path are rejected."""
    client = _client(_library_app(default_public=False), **scope_overrides)
    assert client.get(path).status_code == 400


@pytest.mark.parametrize(
    "method, path",
    [
        ("POST", "/stac../collections"),
        ("GET", "/stac../search"),
        ("GET", "/stacx/search"),
        # checked as "/stac/collections/x" (public), while an upstream sharing the
        # ROOT_PATH env var (e.g. stac-fastapi) would strip "/stac" again
        ("DELETE", "/stac/stac/collections/x"),
        ("GET", "/stac/stac/search"),
    ],
)
def test_root_path_boundary(mock_upstream, source_api_server, method, path):
    """ROOT_PATH is only removed at a segment boundary, and only once."""
    app = app_factory(upstream_url=source_api_server, root_path="/stac")
    response = _client(app).request(method, path)
    assert response.status_code in (400, 404)
    assert mock_upstream.call_count == 0


@pytest.mark.parametrize("root_path", ["/stac", "/stac/"])
@pytest.mark.parametrize(
    "path, forwarded",
    [
        ("/stac", "/"),
        ("/stac/", "/"),
        ("/stac/search", "/search"),
        ("/stac/search/", "/search/"),
    ],
)
def test_root_path_forwarded(
    mock_upstream, source_api_server, root_path, path, forwarded
):
    """The root path, with or without a trailing slash, still works."""
    app = app_factory(upstream_url=source_api_server, root_path=root_path)
    _client(app).get(path)
    assert _forwarded_path(mock_upstream, path) == forwarded


def test_root_path_trailing_slash_links_followable(
    source_api_server, source_api_responses
):
    """With ROOT_PATH="/stac/", links point at paths the proxy accepts."""
    source_api_responses["/"]["GET"] = {
        "links": [{"rel": "data", "href": f"{source_api_server}/collections"}]
    }
    app = app_factory(
        upstream_url=source_api_server,
        root_path="/stac/",
        wait_for_upstream=False,
        check_conformance=False,
    )
    with _client(app) as client:
        [link] = client.get("/stac/").json()["links"]
        assert link["href"] == "http://testserver/stac/collections"
        assert client.get(link["href"]).status_code == 200


@pytest.mark.parametrize(
    "path", ["/collections%252Fc", "/collections/c/items/..%2F..%2Fd", "/a%5Cb"]
)
def test_custom_proxy_rejects_ambiguous_paths(mock_upstream, source_api_server, path):
    """A proxy built on configure_app and ReverseProxyHandler needs no opt-in."""
    app = FastAPI()
    configure_app(
        app,
        Settings(
            upstream_url=source_api_server,
            oidc_discovery_url=OIDC_DISCOVERY_URL,
            default_public=True,
        ),
    )
    proxy = ReverseProxyHandler(upstream=source_api_server)
    app.add_api_route("/{path:path}", proxy.proxy_request, methods=["GET", "DELETE"])
    assert _client(app).get(path).status_code == 400
    assert mock_upstream.call_count == 0


def test_non_utf8_query_rejected_as_invalid_query(mock_upstream, source_api_server):
    """Starlette can't build request.url for it, so say what's actually wrong."""
    client = _proxy_client(source_api_server, query_string=b"x=\xff")
    response = client.get("/collections")
    assert response.status_code == 400
    assert response.json()["description"] == "Invalid query string."
    assert mock_upstream.call_count == 0


def test_server_root_path_without_proxy_root_path(mock_upstream, source_api_server):
    """
    With uvicorn --root-path and no ROOT_PATH, requests are checked and forwarded
    without the prefix, and Swagger UI's URLs keep it.
    """
    app = app_factory(
        upstream_url=source_api_server,
        wait_for_upstream=False,
        check_conformance=False,
        swagger_ui_init_oauth={"clientId": "stac"},  # serve the proxy's Swagger UI
    )
    client = _client(app, root_path="/stac")

    assert client.delete("/stac/collections/x").status_code == 401  # private
    client.get("/stac/search")
    assert _forwarded_path(mock_upstream, "/stac/search") == "/search"
    [request] = mock_upstream.call_args[0]
    assert "filter" in request.url.params

    html = client.get("/stac/api.html").text
    assert "'/stac/api'" in html
    assert "/stac/docs/oauth2-redirect" in html


@pytest.mark.parametrize(
    "path",
    [
        # fullwidth "../" becomes a dot segment to an NFKC-normalizing upstream
        "/collections/public/%EF%BC%8E%EF%BC%8E%EF%BC%8Fprivate/items",
        "/collections/c/items/a%EF%BC%85b",  # fullwidth "%"
        # fullwidth letters: a policy keyed on the id would see "\uff53\uff45..."
        # while a normalizing gateway serves "secret"
        "/collections/%EF%BD%93%EF%BD%85%EF%BD%83%EF%BD%92%EF%BD%85%EF%BD%94/items",
        "/%EF%BD%93%EF%BD%85%EF%BD%81%EF%BD%92%EF%BD%83%EF%BD%88",  # "search"
        # decomposed "\u00e9" and "\u00b2" (trade-off: such ids aren't reachable)
        "/collections/c/items/cafe%CC%81",
        "/collections/c/items/km%C2%B2",
    ],
)
def test_unicode_normalizable_paths_rejected(mock_upstream, source_api_server, path):
    """Paths an upstream could Unicode-normalize into something else aren't forwarded."""
    assert _proxy_client(source_api_server).get(path).status_code in (400, 404)
    assert mock_upstream.call_count == 0


def test_app_root_path_with_trailing_slash(mock_upstream, source_api_server):
    """An app root path given as "/stac/" is removed like "/stac"."""
    app = app_factory(
        upstream_url=source_api_server,
        wait_for_upstream=False,
        check_conformance=False,
    )
    _client(app, root_path="/stac/").get("/stac/search")
    assert _forwarded_path(mock_upstream, "/stac/search") == "/search"


def test_case_variant_doubled_root_path_rejected(mock_upstream, source_api_server):
    """A case-insensitive upstream sharing ROOT_PATH would strip "/STAC" too."""
    app = app_factory(upstream_url=source_api_server, root_path="/stac")
    response = _client(app).get("/stac/STAC/collections/x/items")
    assert response.status_code == 404
    assert mock_upstream.call_count == 0


def test_exact_root_path_serves_landing_page(mock_upstream, source_api_server):
    """GET ROOT_PATH itself reaches the landing page, not a redirect to ROOT_PATH/."""
    app = app_factory(
        upstream_url=source_api_server,
        root_path="/stac",
        wait_for_upstream=False,
        check_conformance=False,
    )
    response = _client(app).get("/stac", follow_redirects=False)
    assert response.status_code == 200
    assert _forwarded_path(mock_upstream, "/stac") == "/"


def test_mounted_custom_proxy_forwards_checked_path(mock_upstream, source_api_server):
    """
    A custom proxy mounted under a sub-path forwards the path the checks saw, so
    "/proxy/collections" (no rule matches: public) isn't forwarded as "/collections".
    """
    from starlette.applications import Starlette
    from starlette.routing import Route

    from stac_auth_proxy.handlers import ReverseProxyHandler

    app = FastAPI()
    configure_app(
        app,
        Settings(
            upstream_url=source_api_server,
            oidc_discovery_url=OIDC_DISCOVERY_URL,
            default_public=True,
        ),
    )
    proxy = ReverseProxyHandler(upstream=source_api_server)
    app.mount(
        "/proxy",
        Starlette(
            routes=[Route("/{path:path}", proxy.proxy_request, methods=["POST"])]
        ),
    )
    _client(app).post("/proxy/collections")
    assert _forwarded_path(mock_upstream, "/proxy/collections") == "/proxy/collections"
