# STAC Auth Proxy Helm Chart

A Helm chart for deploying [STAC Auth Proxy](https://developmentseed.org/stac-auth-proxy) on Kubernetes.

## Overview

This chart deploys a reverse proxy that adds authentication and authorization capabilities to your STAC API using OpenID Connect (OIDC).

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- An OIDC provider (e.g., Keycloak, Auth0, Google, etc.)
- A STAC API backend

## Installation

```bash
helm install stac-auth-proxy ./stac-auth-proxy \
  --set env.UPSTREAM_URL=https://your-stac-api.example.com \
  --set env.OIDC_DISCOVERY_URL=https://your-oidc-provider.example.com/.well-known/openid-configuration \
  --set ingress.host=stac-proxy.example.com
```

## Configuration

### Required Values

| Parameter | Description |
|-----------|-------------|
| `env.UPSTREAM_URL` | URL of the upstream STAC API |
| `env.OIDC_DISCOVERY_URL` | OpenID Connect discovery URL |
| `ingress.host` | Hostname for the ingress |

### Common Configurations

See [`values.yaml`](./values.yaml) for all available configuration options, including:

- **Authentication**: Configure OIDC settings and endpoint protection
- **Resources**: Set CPU/memory limits and requests
- **Ingress**: Configure TLS, annotations, and hostname
- **Security**: Pod and container security contexts

### Example: Custom Values File

```yaml
# custom-values.yaml
image:
  tag: "v1.0.0"

ingress:
  host: "my-stac-api.example.com"

env:
  UPSTREAM_URL: "https://stac-api.internal:8080"
  OIDC_DISCOVERY_URL: "https://my-auth.example.com/.well-known/openid-configuration"
  DEFAULT_PUBLIC: false
```

Install with custom values:

```bash
helm install stac-auth-proxy ./stac-auth-proxy -f custom-values.yaml
```

## Upgrading

```bash
helm upgrade stac-auth-proxy ./stac-auth-proxy -f custom-values.yaml
```

## Uninstalling

```bash
helm uninstall stac-auth-proxy
```

## Testing

Run unit tests to validate chart templates:

```bash
helm unittest helm/
```

Requires the [helm-unittest](https://github.com/helm-unittest/helm-unittest) plugin:

```bash
helm plugin install https://github.com/helm-unittest/helm-unittest
```

## Documentation

For more information about STAC Auth Proxy features and configuration:
- [Project Documentation](https://developmentseed.org/stac-auth-proxy)
- [GitHub Repository](https://github.com/developmentseed/stac-auth-proxy)
