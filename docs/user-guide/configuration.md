# Configuration

The application is configurable via environment variables.

## Core

### `UPSTREAM_URL`

: STAC API URL

    - **Type:** HTTP(S) URL
    - **Required:** Yes
    - **Example:** `https://your-stac-api.com/stac`

### `WAIT_FOR_UPSTREAM`

: Wait for upstream API to become available before starting proxy

    - **Type:** boolean
    - **Required:** No, defaults to `true`
    - **Example:** `false`, `1`, `True`

### `CHECK_CONFORMANCE`

: Ensure upstream API conforms to required conformance classes before starting proxy

    - **Type:** boolean
    - **Required:** No, defaults to `true`
    - **Example:** `false`, `1`, `True`

### `ENABLE_COMPRESSION`

: Enable response compression

    - **Type:** boolean
    - **Required:** No, defaults to `true`
    - **Example:** `false`, `1`, `True`

### `HEALTHZ_PREFIX`

: Path prefix for health check endpoints

    - **Type:** string
    - **Required:** No, defaults to `/healthz`
    - **Example:** `''` (disabled)

### `OVERRIDE_HOST`

: Override the host header before forwarding requests to the upstream API.

    - **Type:** boolean
    - **Required:** No, defaults to `true`
    - **Example:** `false`, `1`, `True`

    > [!TIP]
    > **Default (`true`):** Overrides the [`Host` header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Host) in requests sent to the upstream API to match the upstream API origin, enabling proper `link` element construction via the [`Forwarded` header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Forwarded).
    >
    > **Disable (`false`):** Preserves the original `Host` header in requests sent to the upstream API so that the upstream API can use it when generating `link` elements instead of relying on proxy headers.

### `ROOT_PATH`

: Path prefix for the proxy API

    - **Type:** string
    - **Required:** No, defaults to `''` (root path)
    - **Example:** `/api/v1`

    > [!NOTE]
    > This is independent of the upstream API's path. The proxy will handle removing this prefix from incoming requests and adding it to outgoing links.

## Authentication

### `OIDC_DISCOVERY_URL`

: OpenID Connect discovery document URL

    - **Type:** HTTP(S) URL
    - **Required:** Yes
    - **Example:** `https://auth.example.com/.well-known/openid-configuration`

### `OIDC_DISCOVERY_INTERNAL_URL`

: Internal network OpenID Connect discovery document URL

    - **Type:** HTTP(S) URL
    - **Required:** No, defaults to the value of `OIDC_DISCOVERY_URL`
    - **Example:** `http://auth/.well-known/openid-configuration`

### `ALLOWED_JWT_AUDIENCES`

: Unique identifier(s) of API resource server(s)

    - **Type:** string
    - **Required:** No
    - **Example:** `https://auth.example.audience.1.net,https://auth.example.audience.2.net`

    > [!NOTE]
    > A comma-separated list of the intended recipient(s) of the JWT. At least one audience value must match the `aud` (audience) claim present in the incoming JWT. If unset, the API will not impose a check on the `aud` claim

### `DEFAULT_PUBLIC`

: Default access policy for endpoints

    - **Type:** boolean
    - **Required:** No, defaults to `false`
    - **Example:** `false`, `1`, `True`

### `PRIVATE_ENDPOINTS`

: Endpoints explicitly marked as requiring authentication and possibly scopes

    - **Type:** JSON object mapping regex patterns to HTTP methods OR tuples of an HTTP method and string representing required scopes
    - **Required:** No, defaults to the following:
    ```json
    {
      "^/collections$": ["POST"],
      "^/collections/([^/]+)$": ["PUT", "PATCH", "DELETE"],
      "^/collections/([^/]+)/items$": ["POST"],
      "^/collections/([^/]+)/items/([^/]+)$": ["PUT", "PATCH", "DELETE"],
      "^/collections/([^/]+)/bulk_items$": ["POST"]
    }
    ```

### `PUBLIC_ENDPOINTS`

: Endpoints explicitly marked as not requiring authentication, used when `DEFAULT_PUBLIC == False`

    - **Type:** JSON object mapping regex patterns to HTTP methods
    - **Required:** No, defaults to the following:
    ```json
    {
      "^/$": ["GET"],
      "^/api.html$": ["GET"],
      "^/api$": ["GET"],
      "^/conformance$": ["GET"],
      "^/docs/oauth2-redirect": ["GET"],
      "^/healthz": ["GET"]
    }
    ```

### `ENABLE_AUTHENTICATION_EXTENSION`

: Enable authentication extension in STAC API responses

    - **Type:** boolean
    - **Required:** No, defaults to `true`
    - **Example:** `false`, `1`, `True`

## OpenAPI / Swagger UI

### `OPENAPI_SPEC_ENDPOINT`

: Path of OpenAPI specification, used for augmenting spec response with auth configuration

    - **Type:** string or null
    - **Required:** No, defaults to `/api`
    - **Example:** `''` (disabled)

### `OPENAPI_AUTH_SCHEME_NAME`

: Name of the auth scheme to use in the OpenAPI spec

    - **Type:** string
    - **Required:** No, defaults to `oidcAuth`
    - **Example:** `jwtAuth`

### `OPENAPI_AUTH_SCHEME_OVERRIDE`

: Override for the auth scheme in the OpenAPI spec

    - **Type:** JSON object
    - **Required:** No, defaults to `null` (disabled)
    - **Example:**
    ```json
    {
      "type": "http",
      "scheme": "bearer",
      "bearerFormat": "JWT",
      "description": "Paste your raw JWT here. This API uses Bearer token authorization.\n"
    }
    ```

### `SWAGGER_UI_ENDPOINT`

: Path of Swagger UI, used to indicate that a custom Swagger UI should be hosted, typically useful when providing accompanying `SWAGGER_UI_INIT_OAUTH` arguments

    - **Type:** string or null
    - **Required:** No, defaults to `/api.html`
    - **Example:** `''` (disabled)

### `SWAGGER_UI_INIT_OAUTH`

: Initialization options for the [Swagger UI OAuth2 configuration](https://swagger.io/docs/open-source-tools/swagger-ui/usage/oauth2/) on custom Swagger UI

    - **Type:** JSON object
    - **Required:** No, defaults to `null` (disabled)
    - **Example:** `{"clientId": "stac-auth-proxy", "usePkceWithAuthorizationCodeGrant": true}`

## Filtering

### `ITEMS_FILTER_CLS`

: CQL2 expression factor for item-level filtering

    - **Type:** JSON object with class configuration
    - **Required:** No, defaults to `null` (disabled)
    - **Example:** `stac_auth_proxy.filters:Opa`, `stac_auth_proxy.filters:Template`, `my_package:OrganizationFilter`

### `ITEMS_FILTER_ARGS`

: Positional arguments for CQL2 expression factor

    - **Type:** List of positional arguments used to initialize the class
    - **Required:** No, defaults to `[]`
    - **Example:** `["org1"]`

### `ITEMS_FILTER_KWARGS`

: Keyword arguments for CQL2 expression factor

    - **Type:** Dictionary of keyword arguments used to initialize the class
    - **Required:** No, defaults to `{}`
    - **Example:** `{"field_name": "properties.organization"}`

### `ITEMS_FILTER_PATH`

: Regex pattern used to identify request paths that require the application of the items filter

    - **Type:** Regex string
    - **Required:** No, defaults to `^(/collections/([^/]+)/items(/[^/]+)?$|/search$)`
    - **Example:** `^(/collections/([^/]+)/items(/[^/]+)?$|/search$|/custom$)`

### `COLLECTIONS_FILTER_CLS`

: CQL2 expression factor for collection-level filtering

    - **Type:** JSON object with class configuration
    - **Required:** No, defaults to `null` (disabled)
    - **Example:** `stac_auth_proxy.filters:Opa`, `stac_auth_proxy.filters:Template`, `my_package:OrganizationFilter`

### `COLLECTIONS_FILTER_ARGS`

: Positional arguments for CQL2 expression factor

    - **Type:** List of positional arguments used to initialize the class
    - **Required:** No, defaults to `[]`
    - **Example:** `["org1"]`

### `COLLECTIONS_FILTER_KWARGS`

: Keyword arguments for CQL2 expression factor

    - **Type:** Dictionary of keyword arguments used to initialize the class
    - **Required:** No, defaults to `{}`
    - **Example:** `{"field_name": "properties.organization"}`

### `COLLECTIONS_FILTER_PATH`

: Regex pattern used to identify request paths that require the application of the collections filter

    - **Type:** Regex string
    - **Required:** No, defaults to `^/collections(/[^/]+)?$`
    - **Example:** `^.*?/collections(/[^/]+)?$`
