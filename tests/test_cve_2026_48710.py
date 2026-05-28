"""
Regression tests for CVE-2026-48710 (BadHost) — Starlette host-header path spoofing.

https://www.cve.org/CVERecord?id=CVE-2026-48710

Vulnerable Starlette (<1.0.1) rebuilds ``request.url`` from the unvalidated
Host header. A request line ``GET /collections`` paired with ``Host: evil.com/?``
makes ``urlparse`` split the reconstructed URL so that:

  * ``scope["path"]``     == "/collections"   (real routed path)
  * ``request.url.path``  == "/"              (attacker-controlled)
  * ``request.url.query`` == "/collections"   (attacker-controlled)

Any middleware that branches on ``request.url.path`` for auth is therefore
inconsistent with the path the ASGI router actually dispatched, which is the
bypass primitive described in the CVE.

These tests assert the *correct* behavior. They fail while the bug is present
(Starlette <1.0.1 with ``EnforceAuthMiddleware`` reading ``request.url.path``)
and pass once it's fixed — either by bumping ``starlette>=1.0.1`` in
pyproject.toml or by switching security-sensitive middleware to
``request.scope["path"]`` (see ``EnforceAuthMiddleware.py:94`` and the five
other middleware that share the pattern).
"""

from fastapi.testclient import TestClient
from utils import AppFactory

BAD_HOST = (
    "evil.com/?"  # in vulnerable Starlette, makes request.url.path resolve to "/"
)


def test_starlette_url_path_matches_scope_path():
    """The Starlette primitive must not let the Host header rewrite request.url.path."""
    from starlette.requests import Request

    scope = {
        "type": "http",
        "scheme": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/collections",
        "raw_path": b"/collections",
        "query_string": b"",
        "headers": [(b"host", BAD_HOST.encode())],
        "server": ("127.0.0.1", 8000),
        "client": ("127.0.0.1", 12345),
    }
    request = Request(scope)
    assert request.url.path == scope["path"], (
        f"Starlette is vulnerable to CVE-2026-48710: request.url.path="
        f"{request.url.path!r} but scope['path']={scope['path']!r}. "
        f"Upgrade starlette>=1.0.1."
    )


def test_enforce_auth_rejects_badhost_default_public_false(source_api_server):
    """
    ``default_public=False`` + ``/`` listed as public_endpoint.

    /collections is private. A BadHost-spoofed request must still be denied —
    the middleware must judge auth from the real routed path, not from a value
    derived from the Host header.
    """
    factory = AppFactory(
        oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
        default_public=False,
        public_endpoints={r"^/$": ["GET"]},
        private_endpoints={},
    )
    app = factory(upstream_url=source_api_server)
    client = TestClient(app)

    # Baseline: unspoofed request to a private endpoint is correctly denied.
    baseline = client.get("/collections")
    assert baseline.status_code == 401

    # CVE-2026-48710: BadHost must not bypass the private-endpoint check.
    exploit = client.get("/collections", headers={"Host": BAD_HOST})
    assert exploit.status_code == 401, (
        f"CVE-2026-48710 bypass: BadHost header turned a 401 into "
        f"{exploit.status_code}. EnforceAuthMiddleware judged auth from a "
        f"Host-derived path instead of scope['path']."
    )


def test_enforce_auth_rejects_badhost_default_public_true(source_api_server):
    """
    ``default_public=True`` + ``/admin`` declared private.

    /admin is private. A BadHost-spoofed request must still be denied.
    """
    factory = AppFactory(
        oidc_discovery_url="https://example-stac-api.com/.well-known/openid-configuration",
        default_public=True,
        public_endpoints={},
        private_endpoints={r"^/admin": ["GET"]},
    )
    app = factory(upstream_url=source_api_server)
    client = TestClient(app)

    baseline = client.get("/admin")
    assert baseline.status_code == 401

    exploit = client.get("/admin", headers={"Host": BAD_HOST})
    assert exploit.status_code == 401, (
        f"CVE-2026-48710 bypass: BadHost header turned a 401 into "
        f"{exploit.status_code}. EnforceAuthMiddleware judged auth from a "
        f"Host-derived path instead of scope['path']."
    )
