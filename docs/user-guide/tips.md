# Tips

## CORS

By default, the STAC Auth Proxy handles [CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS) locally. OPTIONS preflight requests are answered directly by the proxy, and CORS headers are included on all responses — including `401` and `403` errors — so that browser clients can read error details. This behavior is configured with the `CORS_*` environment variables (see [Configuration](configuration.md#cors)).

The defaults are designed to work out of the box for browser-based clients that send `Authorization` headers:

- `CORS_ALLOW_ORIGINS=*` — all origins are accepted
- `CORS_ALLOW_CREDENTIALS=true` — required because frontends will send `Authorization` headers
- `CORS_ALLOW_METHODS=*` and `CORS_ALLOW_HEADERS=*` — all methods and headers are accepted

Because the [CORS specification](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS/Errors/CORSNotSupportingCredentials) forbids `Access-Control-Allow-Origin: *` when credentials are enabled, the proxy automatically reflects the request's `Origin` header back in the response instead of sending a literal `*`.[^CORSNotSupportingCredentials]

To restrict access to specific origins:

```sh
CORS_ALLOW_ORIGINS=https://my-app.example.com,https://staging.example.com
```

### Upstream CORS handling

If you prefer the upstream API to handle CORS instead, set `PROXY_OPTIONS=true`. In this mode, OPTIONS requests are forwarded to the upstream API and the proxy does not add CORS headers.

Because the STAC Auth Proxy introduces authentication, the upstream API's CORS settings may need adjustment to support credentials. In most cases, this means:

- [`Access-Control-Allow-Credentials`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Access-Control-Allow-Credentials) must be `true`
- [`Access-Control-Allow-Origin`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Access-Control-Allow-Origin) must _not_ be `*`[^CORSNotSupportingCredentials]

[^CORSNotSupportingCredentials]: https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS/Errors/CORSNotSupportingCredentials

## Root Paths

The proxy can be optionally served from a non-root path (e.g., `/api/v1`). Additionally, the proxy can optionally proxy requests to an upstream API served from a non-root path (e.g., `/stac`). To handle this, the proxy will:

- Remove the `ROOT_PATH` from incoming requests before forwarding to the upstream API
- Remove the proxy's prefix from all links in STAC API responses
- Add the `ROOT_PATH` prefix to all links in STAC API responses
- Update the OpenAPI specification to include the `ROOT_PATH` in the servers field
- Handle requests that don't match the `ROOT_PATH` with a 404 response
- Handle requests whose path, after removing the `ROOT_PATH` (or, when it is unset, the app's own root path), still starts with the app's own root path (e.g. `/stac/stac/collections`) with a 404 response

### Upstream APIs served from a non-root path

Give the upstream API its prefix with `uvicorn --root-path` (or `UVICORN_ROOT_PATH`), or by putting the prefix in [`UPSTREAM_URL`](configuration.md#upstream_url) (e.g. `UPSTREAM_URL=http://stac:8080/stac/`). Do **not** rely on an app-level root path in the upstream, such as stac-fastapi's `ROOT_PATH` environment variable or `FastAPI(root_path="/stac")`.

An app-level root path makes the upstream strip the prefix only when it is present, so `/stac/collections/x` and `/collections/x` reach the same route. The proxy checks auth and applies filters to the path it receives, not the path the upstream routes on. A request for `/stac/collections/x` will not match a private endpoint or filter rule written for `/collections/{id}`, but the upstream still serves it as `/collections/x`. This lets clients skip authentication and record-level filtering.

> [!WARNING]
> If the upstream is a stac-fastapi app, do not set its `ROOT_PATH` environment variable. The proxy reads an environment variable with the same name, so sharing one environment between the two containers will set both.

If other apps share the same host (e.g. the proxy at `/stac` and a tiler at `/raster`), their links would also get `ROOT_PATH` added by mistake. Set `ROOT_PATH_SKIP_PREFIXES` to those paths (e.g. `/raster`) so the proxy leaves them alone.

## Request Paths

Auth, filter and transaction checks match on the request path, so the proxy only forwards a path when it's sure the upstream will act on the same path it checked. Any other request gets a `400 Bad Request` (`{"code": "BadRequest", "description": "Invalid request path."}`) without reaching the upstream.

A path is forwarded when, once percent-decoded:

- every segment is non-empty, and is neither `.` nor `..`;
- every character is a letter or digit (including non-ASCII), a space, or one of `` -._~!$&'()*+,=:@"<>[]^`{|} ``;
- Unicode normalization (NFKC) leaves it unchanged, so fullwidth or decomposed characters (e.g. `ｓ`, NFD `é`, `²`) are rejected: a normalizing gateway or upstream could act on a different path than auth and filters checked.

So `%`, `?`, `#`, `;`, `\` and control characters are rejected. Records whose ids contain them can't be reached through the proxy.

Requests whose query string isn't valid UTF-8 are rejected with `400` (`"Invalid query string."`).

A single trailing slash is allowed and forwarded as sent. Many upstreams treat `/collections/` as `/collections`, so auth, filter and transaction rules match a path with a trailing slash as if it had none.

Requests whose URL, as rebuilt from the scheme and `Host` header (e.g. a client-supplied `X-Forwarded-Proto` copied into the scheme by an ASGI adapter), has a different path from the one being routed are rejected too, before any check runs.

## Non-OIDC Workaround

If the upstream server utilizes RS256 JWTs but does not utilize a proper OIDC server, the proxy can be configured to work around this by setting the `OIDC_DISCOVERY_URL` to a statically-hosted OIDC discovery document that points to a valid JWKS endpoint.

## Swagger UI Direct JWT Input

Rather than performing the login flow, the Swagger UI can be configured to accept direct JWT as input with the the following configuration:

```sh
OPENAPI_AUTH_SCHEME_NAME=jwtAuth
OPENAPI_AUTH_SCHEME_OVERRIDE='{
  "type": "http",
  "scheme": "bearer",
  "bearerFormat": "JWT",
  "description": "Paste your raw JWT here. This API uses Bearer token authorization."
}'
```

## Non-proxy Configuration

While the STAC Auth Proxy is designed to work out-of-the-box as an application, it might not address every projects needs. When the need for customization arises, the codebase can instead be treated as a library of components that can be used to augment a FastAPI server.

This may look something like the following:

```py
from fastapi import FastAPI
from stac_fastapi.api.app import StacApi
from stac_auth_proxy import configure_app, Settings as StacAuthSettings

# Create Auth Settings
auth_settings = StacAuthSettings(
  upstream_url='https://stac-server',  # Dummy value, we don't make use of this value in non-proxy mode
  oidc_discovery_url='https://auth-server/.well-known/openid-configuration',
)

# Setup App
app = FastAPI( ... )

# Apply STAC Auth Proxy middleware
configure_app(app, auth_settings)

# Setup STAC API
api = StacApi( app, ... )
```

> [!NOTE]
> Only the last [request path](#request-paths) check applies to the app's own routes, which are free to use any characters. The others apply to requests forwarded by `ReverseProxyHandler`, so a custom proxy built on it gets them too.

> [!IMPORTANT]
> Avoid using `build_lifespan()` when operating in non-proxy mode, as we are unable to check for the non-existent upstream API.

> [!IMPORTANT]
> If the app is served from a non-root path (`FastAPI(root_path=...)`, stac-fastapi's `ROOT_PATH`, or `uvicorn --root-path`), the proxy removes that root path for its checks, as Starlette does when routing, and puts it back before routing. Rules written for `/collections/{id}` therefore match `/stac/collections/x`, whether or not the `root_path` setting is also set, while the app's routes, mounts and docs see the usual request.
