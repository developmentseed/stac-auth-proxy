# Middleware Stack

Aside from the actual communication with the upstream STAC API, the majority of the proxy's functionality occurs within a chain of middlewares. Each request passes through this chain, wherein each middleware performs a specific task. The middleware chain is ordered from last added (first to run) to first added (last to run).

> [!TIP]
> If you want to apply just the middleware onto your existing FastAPI application, you can do this with [`configure_app`][stac_auth_proxy.configure_app] rather than setting up a separate proxy application.

> [!IMPORTANT]
> The order of middleware execution is **critical**. For example, `RemoveRootPathMiddleware` must run before `EnforceAuthMiddleware` so that authentication decisions are made on the correct path after root path removal.

1.  **[`CompressionMiddleware`](https://github.com/developmentseed/starlette-cramjam)**

    - **Enabled if:** [`ENABLE_COMPRESSION`](../../user-guide/configuration#enable_compression) is enabled
    - Handles response compression
    - Reduces response size for better performance

2.  **[`RemoveRootPathMiddleware`][stac_auth_proxy.middleware.RemoveRootPathMiddleware]**

    - **Enabled if:** [`ROOT_PATH`](../../user-guide/configuration#root_path) is configured
    - Removes the application root path from incoming requests
    - Ensures requests are properly routed to upstream API

3.  **[`ProcessLinksMiddleware`][stac_auth_proxy.middleware.ProcessLinksMiddleware]**

    - **Enabled if:** [`ROOT_PATH`](../../user-guide/configuration#root_path) is set or [`UPSTREAM_URL`](../../user-guide/configuration#upstream_url) path is not `"/"`
    - Updates links in JSON responses to handle root path and upstream URL path differences
    - Removes upstream URL path from links and adds root path if configured

4.  **[`EnforceAuthMiddleware`][stac_auth_proxy.middleware.EnforceAuthMiddleware]**

    - **Enabled if:** Always active (core authentication middleware)
    - Handles authentication and authorization
    - Configurable public/private endpoints via [`PUBLIC_ENDPOINTS`](../../user-guide/configuration#public_endpoints) and [`PRIVATE_ENDPOINTS`](../../user-guide/configuration#private_endpoints)
    - OIDC integration via [`OIDC_DISCOVERY_INTERNAL_URL`](../../user-guide/configuration#oidc_discovery_internal_url)
    - JWT audience validation via [`ALLOWED_JWT_AUDIENCES`](../../user-guide/configuration#allowed_jwt_audiences)
    - Places auth token payload in request state

5.  **[`AddProcessTimeHeaderMiddleware`][stac_auth_proxy.middleware.AddProcessTimeHeaderMiddleware]**

    - **Enabled if:** Always active (monitoring middleware)
    - Adds processing time headers to responses
    - Useful for monitoring and debugging

6.  **[`Cql2BuildFilterMiddleware`][stac_auth_proxy.middleware.Cql2BuildFilterMiddleware]**

    - **Enabled if:** [`ITEMS_FILTER_CLS`](../../user-guide/configuration#items_filter_cls) or [`COLLECTIONS_FILTER_CLS`](../../user-guide/configuration#collections_filter_cls) is configured
    - Builds CQL2 filters based on request context/state
    - Places [CQL2 expression](http://developmentseed.org/cql2-rs/latest/python/#cql2.Expr) in request state

7.  **[`Cql2RewriteLinksFilterMiddleware`][stac_auth_proxy.middleware.Cql2RewriteLinksFilterMiddleware]**

    - **Enabled if:** [`ITEMS_FILTER_CLS`](../../user-guide/configuration#items_filter_cls) or [`COLLECTIONS_FILTER_CLS`](../../user-guide/configuration#collections_filter_cls) is configured
    - Rewrites filter parameters in response links to remove applied filters
    - Ensures links in responses show the original filter state

8.  **[`Cql2ApplyFilterQueryStringMiddleware`][stac_auth_proxy.middleware.Cql2ApplyFilterQueryStringMiddleware]**

    - **Enabled if:** [`ITEMS_FILTER_CLS`](../../user-guide/configuration#items_filter_cls) or [`COLLECTIONS_FILTER_CLS`](../../user-guide/configuration#collections_filter_cls) is configured
    - Retrieves [CQL2 expression](http://developmentseed.org/cql2-rs/latest/python/#cql2.Expr) from request state
    - Augments `GET` requests with CQL2 filter by appending to querystring

9.  **[`Cql2ApplyFilterBodyMiddleware`][stac_auth_proxy.middleware.Cql2ApplyFilterBodyMiddleware]**

    - **Enabled if:** [`ITEMS_FILTER_CLS`](../../user-guide/configuration#items_filter_cls) or [`COLLECTIONS_FILTER_CLS`](../../user-guide/configuration#collections_filter_cls) is configured
    - Retrieves [CQL2 expression](http://developmentseed.org/cql2-rs/latest/python/#cql2.Expr) from request state
    - Augments `POST`/`PUT`/`PATCH` requests with CQL2 filter by modifying body

10. **[`Cql2ValidateResponseBodyMiddleware`][stac_auth_proxy.middleware.Cql2ValidateResponseBodyMiddleware]**

    - **Enabled if:** [`ITEMS_FILTER_CLS`](../../user-guide/configuration#items_filter_cls) or [`COLLECTIONS_FILTER_CLS`](../../user-guide/configuration#collections_filter_cls) is configured
    - Retrieves [CQL2 expression](http://developmentseed.org/cql2-rs/latest/python/#cql2.Expr) from request state
    - Validates response against CQL2 filter for non-filterable endpoints

11. **[`OpenApiMiddleware`][stac_auth_proxy.middleware.OpenApiMiddleware]**

    - **Enabled if:** [`OPENAPI_SPEC_ENDPOINT`](../../user-guide/configuration#openapi_spec_endpoint) is set
    - Modifies OpenAPI specification based on endpoint configuration, adding security requirements
    - Configurable via [`OPENAPI_AUTH_SCHEME_NAME`](../../user-guide/configuration#openapi_auth_scheme_name) and [`OPENAPI_AUTH_SCHEME_OVERRIDE`](../../user-guide/configuration#openapi_auth_scheme_override)

12. **[`AuthenticationExtensionMiddleware`][stac_auth_proxy.middleware.AuthenticationExtensionMiddleware]**
    - **Enabled if:** [`ENABLE_AUTHENTICATION_EXTENSION`](../../user-guide/configuration#enable_authentication_extension) is enabled
    - Adds authentication extension information to STAC responses
    - Annotates links with authentication requirements based on [`PUBLIC_ENDPOINTS`](../../user-guide/configuration#public_endpoints) and [`PRIVATE_ENDPOINTS`](../../user-guide/configuration#private_endpoints)
