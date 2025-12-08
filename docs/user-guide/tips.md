# Tips

## CORS

The STAC Auth Proxy does not modify the [CORS response headers](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS#the_http_response_headers) from the upstream STAC API. All CORS configuration must be handled by the upstream API.

Because the STAC Auth Proxy introduces authentication, the upstream API’s CORS settings may need adjustment to support credentials. In most cases, this means:

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

> [!IMPORTANT]
> Avoid using `build_lifespan()` when operating in non-proxy mode, as we are unable to check for the non-existent upstream API.
