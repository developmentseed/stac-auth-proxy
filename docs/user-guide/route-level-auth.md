# Route-Level Authorization

Route-level authorization can provide a base layer of security for the simplest use cases. This typically looks like:

- the entire catalog being private, available only to authenticated users
- most of the catalog being public, available to anonymous or authenticated users. However, a subset of endpoints (typically the [transactions extension](https://github.com/stac-api-extensions/transaction) endpoints) are only available to all or a subset of authenticated users

## Configuration Variables

Route-level authorization is controlled by three key environment variables:

- **[`DEFAULT_PUBLIC`](../../configuration/#default_public)**: Sets the default access policy for all endpoints
- **[`PUBLIC_ENDPOINTS`](../../configuration/#public_endpoints)**: Marks endpoints as not requiring authentication (used only when `DEFAULT_PUBLIC=false`). By default, we keep the catalog root, OpenAPI spec, Swagger UI, Swagger UI auth redirect, and the proxy health endpoint as public. Note that these are all endpoints that don't serve actual STAC data; they only acknowledge the presence of a STAC catalog. This is defined by a mapping of regex path expressions to arrays of HTTP methods.
- **[`PRIVATE_ENDPOINTS`](../../configuration/#private_endpoints)**: Marks endpoints as requiring authentication. By default, the transactions endpoints are all marked as private. This is defined by a mapping of regex path expressions to arrays of either HTTP methods or tuples of HTTP methods and space-separated required scopes.

> [!TIP]
>
> Users typically don't need to specify both `PRIVATE_ENDPOINTS` and `PUBLIC_ENDPOINTS`.

## Strategies

### Private by Default

Make the entire STAC API private, requiring authentication for all endpoints.

> [!NOTE]
>
> This is the out-of-the-box configuration of the STAC Auth Proxy.

**Configuration**

```bash
# Set default policy to private
DEFAULT_PUBLIC=false

# The default public endpoints are typically sufficient. Otherwise, they can be specified.
# PUBLIC_ENDPOINTS='{ ... }'
```

**Behavior**

- All endpoints require authentication by default
- Only explicitly listed endpoints in `PUBLIC_ENDPOINTS` are accessible without authentication. By default, these are endpoints that don't reveal STAC data
- Useful for internal or enterprise STAC APIs where all data should be protected

### Public by Default with Protected Write Operations

Make the STAC API mostly public for read operations, but require authentication for write operations (transactions extension).

**Configuration**

```bash
# Set default policy to public
DEFAULT_PUBLIC=true

# The default private endpoints are typically sufficient. Otherwise, they can be specified.
# PRIVATE_ENDPOINTS='{ ... }'
```

**Behavior**

- Read operations (GET requests) are accessible to everyone
- Write operations require authentication
- Default configuration matches this pattern
- Ideal for public STAC catalogs where data discovery is open but modifications are restricted

### Authenticated Access with Scope-based Authorization

For a level of control beyond simple anonymous vs. authenticated status, the proxy can be configured so that path/method access requires JWTs containing particular permissions in the form of the [scopes claim](https://datatracker.ietf.org/doc/html/rfc8693#name-scope-scopes-claim).

**Configuration**

For granular permissions on a public API:

```bash
# Set default policy to public
DEFAULT_PUBLIC=true

# Require specific scopes for write operations
PRIVATE_ENDPOINTS='{
  "^/collections$": [["POST", "collection:create"]],
  "^/collections/([^/]+)$": [["PUT", "collection:update"], ["PATCH", "collection:update"], ["DELETE", "collection:delete"]],
  "^/collections/([^/]+)/items$": [["POST", "item:create"]],
  "^/collections/([^/]+)/items/([^/]+)$": [["PUT", "item:update"], ["PATCH", "item:update"], ["DELETE", "item:delete"]],
  "^/collections/([^/]+)/bulk_items$": [["POST", "item:create"]]
}'
```

For role-based permissions on a private API:

```bash
# Set default policy to private
DEFAULT_PUBLIC=false

# Require specific scopes for write operations
PRIVATE_ENDPOINTS='{
  "^/collections$": [["POST", "admin"]],
  "^/collections/([^/]+)$": [["PUT", "admin"], ["PATCH", "admin"], ["DELETE", "admin"]],
  "^/collections/([^/]+)/items$": [["POST", "editor"]],
  "^/collections/([^/]+)/items/([^/]+)$": [["PUT", "editor"], ["PATCH", "editor"], ["DELETE", "editor"]],
  "^/collections/([^/]+)/bulk_items$": [["POST", "editor"]]
}'
```

**Behavior**

- Users must be authenticated AND have the required scope(s)
- Different HTTP methods can require different scopes
- Scopes are checked against the user's JWT scope claim
- Unauthorized requests receive a 401 Unauthorized response

> [!TIP]
>
> Multiple scopes can be provided in a space-separated format, such as `["POST", "scope_a scope_b scope_c"]`. These scope requirements are applied with AND logic, meaning that the incoming JWT must contain all the mentioned scopes.
