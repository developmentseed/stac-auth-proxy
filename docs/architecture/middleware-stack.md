# Middleware Stack

Aside from the actual communication with the upstream STAC API, the majority of the proxy's functionality occurs within a chain of middlewares. Each request passes through this chain, wherein each middleware performs a specific task:

1. **[`EnforceAuthMiddleware`][stac_auth_proxy.middleware.EnforceAuthMiddleware]**

      - Handles authentication and authorization
      - Configurable public/private endpoints
      - OIDC integration
      - Places auth token payload in request state

1. **[`Cql2BuildFilterMiddleware`][stac_auth_proxy.middleware.Cql2BuildFilterMiddleware]**

      - Builds CQL2 filters based on request context/state
      - Places [CQL2 expression](http://developmentseed.org/cql2-rs/latest/python/#cql2.Expr) in request state

2. **[`Cql2ApplyFilterQueryStringMiddleware`][stac_auth_proxy.middleware.Cql2ApplyFilterQueryStringMiddleware]**

      - Retrieves [CQL2 expression](http://developmentseed.org/cql2-rs/latest/python/#cql2.Expr) from request state
      - Augments `GET` requests with CQL2 filter by appending to querystring

3. **[`Cql2ApplyFilterBodyMiddleware`][stac_auth_proxy.middleware.Cql2ApplyFilterBodyMiddleware]**

      - Retrieves [CQL2 expression](http://developmentseed.org/cql2-rs/latest/python/#cql2.Expr) from request state
      - Augments `` POST`/`PUT`/`PATCH `` requests with CQL2 filter by modifying body

4. **[`Cql2ValidateResponseBodyMiddleware`][stac_auth_proxy.middleware.Cql2ValidateResponseBodyMiddleware]**

      - Retrieves [CQL2 expression](http://developmentseed.org/cql2-rs/latest/python/#cql2.Expr) from request state
      - Validates response against CQL2 filter for non-filterable endpoints

5. **[`OpenApiMiddleware`][stac_auth_proxy.middleware.OpenApiMiddleware]**

      - Modifies OpenAPI specification based on endpoint configuration, adding security requirements
      - Only active if `openapi_spec_endpoint` is configured

6. **[`AddProcessTimeHeaderMiddleware`][stac_auth_proxy.middleware.AddProcessTimeHeaderMiddleware]**
      - Adds processing time headers
      - Useful for monitoring/debugging
