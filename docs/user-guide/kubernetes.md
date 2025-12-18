# Kubernetes Deployment

Deploy STAC Auth Proxy to Kubernetes using the Helm chart.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+

## Installation

```bash
helm registry login ghcr.io

helm install stac-auth-proxy oci://ghcr.io/developmentseed/stac-auth-proxy/charts/stac-auth-proxy \
  --set env.UPSTREAM_URL=https://your-stac-api.com/stac \
  --set env.OIDC_DISCOVERY_URL=https://your-auth-server/.well-known/openid-configuration \
  --set ingress.host=stac-proxy.your-domain.com
```

### Configuration

| Parameter                | Description                                   | Required | Default |
| ------------------------ | --------------------------------------------- | -------- | ------- |
| `env.UPSTREAM_URL`       | URL of the STAC API to proxy                  | Yes      | -       |
| `env.OIDC_DISCOVERY_URL` | OpenID Connect discovery document URL         | Yes      | -       |
| `env`                    | Environment variables passed to the container | No       | `{}`    |
| `ingress.enabled`        | Enable ingress                                | No       | `true`  |
| `ingress.className`      | Ingress class name                            | No       | `nginx` |
| `ingress.host`           | Hostname for the ingress                      | No       | `""`    |
| `ingress.tls.enabled`    | Enable TLS for ingress                        | No       | `true`  |
| `replicaCount`           | Number of replicas                            | No       | `1`     |

For a complete list of values, see the [values.yaml](https://github.com/developmentseed/stac-auth-proxy/blob/main/helm/values.yaml) file.

## Authorization

The chart provides two levels of authorization:

1. **[Route-level authorization](route-level-auth.md)**: Controls which API endpoints are accessible and by whom
2. **[Record-level authorization](record-level-auth.md)**: Filters collections and items based on user permissions

### Route-Level Authorization

Configure via `authorization.route` section in `values.yaml`.

#### Mode: `default` (Recommended)

Public catalog with protected write operations. This is the most common configuration.

```yaml
authorization:
  route:
    mode: "default"
```

This automatically sets `DEFAULT_PUBLIC=true`, making all read endpoints public while requiring authentication for write operations.

#### Mode: `custom`

Define specific public and private endpoints with custom rules.

```yaml
authorization:
  route:
    mode: "custom"
    publicEndpoints:
      "^/collections$": ["GET"]
      "^/search$": ["GET", "POST"]
      "^/api.html$": ["GET"]
      "^/healthz": ["GET"]
    privateEndpoints:
      "^/collections$": [["POST", "collection:create"]]
      "^/collections/([^/]+)$": [["PUT", "collection:update"], ["DELETE", "collection:delete"]]
      "^/collections/([^/]+)/items$": [["POST", "item:create"]]
```

**Endpoint format:**
- `publicEndpoints`: Maps regex paths to HTTP methods arrays
- `privateEndpoints`: Maps regex paths to HTTP methods or `[method, scope]` tuples
  - Scopes define required OAuth2 scopes for the operation

#### Mode: `disabled`

No route-level authorization applied.

```yaml
authorization:
  route:
    mode: "disabled"
```

### Record-Level Authorization

Configure via `authorization.record` section in `values.yaml`.

#### Mode: `disabled` (Default)

No record-level filtering applied. All collections and items are visible to authenticated users.

```yaml
authorization:
  record:
    mode: "disabled"
```

#### Mode: `custom`

Use Python filter classes to control visibility of collections and items.

```yaml
authorization:
  record:
    mode: "custom"
    custom:
      filtersFile: "data/custom_filters.py"
```

This automatically:
- Creates a ConfigMap from your Python file
- Mounts it at `/app/src/stac_auth_proxy/custom_filters.py`
- Sets `COLLECTIONS_FILTER_CLS=stac_auth_proxy.custom_filters:CollectionsFilter`
- Sets `ITEMS_FILTER_CLS=stac_auth_proxy.custom_filters:ItemsFilter`

Review the stac-auth-proxy [documentation for more information on custom filters](record-level-auth.md#custom-filter-factories).

#### Mode: `opa`

Use Open Policy Agent for policy-based filtering.

```yaml
authorization:
  record:
    mode: "opa"
    opa:
      url: "http://opa-service:8181"
      policy: "stac/items/allow"
```

This sets:
- `ITEMS_FILTER_CLS=stac_auth_proxy.filters.opa:Opa`
- `ITEMS_FILTER_ARGS='["http://opa-service:8181", "stac/items/allow"]'`

### Configuration Examples

#### Example 1: Default for public catalog, protected writes

```yaml
authorization:
  route:
    mode: "default"
  record:
    mode: "disabled"
```

#### Example 2: Fully protected catalog

```yaml
authorization:
  route:
    mode: "custom"
    publicEndpoints:
      "^/healthz": ["GET"]
    privateEndpoints:
      "^/collections$": [["GET", "stac:read"], ["POST", "stac:write"]]
      "^/search$": [["GET", "stac:read"], ["POST", "stac:read"]]
  record:
    mode: "custom"
    custom:
      filtersFile: "data/custom_filters.py"
```

### Direct Configuration

Existing charts using `env` variables directly continue to work:

```yaml
env:
  DEFAULT_PUBLIC: "false"
  PUBLIC_ENDPOINTS: '{"^/search$": ["GET"]}'
  PRIVATE_ENDPOINTS: '{"^/collections$": [["POST", "collection:create"]]}'
  ITEMS_FILTER_CLS: "custom.module:Filter"
```

**Environment variables specified in `env` take precedence over `authorization` settings.**

## Management

```bash
# Upgrade
helm upgrade stac-auth-proxy oci://ghcr.io/developmentseed/stac-auth-proxy/charts/stac-auth-proxy

# Uninstall
helm uninstall stac-auth-proxy
```

