# Tips

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
OPENAPI_AUTH_SCHEME_OVERRIDE={"type": "http", "scheme": "bearer", "bearerFormat": "JWT", "description": "Paste your raw JWT here. This API uses Bearer token authorization."}
```

## Runtime Customization

While the project is designed to work out-of-the-box as an application, it might not address every projects needs. When the need for customization arises, the codebase can instead be treated as a library of components that can be used to augment any [ASGI](https://asgi.readthedocs.io/en/latest/)-compliant webserver (e.g. [Django](https://docs.djangoproject.com/en/3.0/topics/async/), [Falcon](https://falconframework.org/), [FastAPI](https://github.com/tiangolo/fastapi), [Litestar](https://litestar.dev/), [Responder](https://responder.readthedocs.io/en/latest/), [Sanic](https://sanic.dev/), [Starlette](https://www.starlette.io/)). Review [`app.py`](https://github.com/developmentseed/stac-auth-proxy/blob/main/src/stac_auth_proxy/app.py) to get a sense of how we make use of the various components to construct a FastAPI application.
