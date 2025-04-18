# STAC Auth Proxy Helm Chart

This Helm chart deploys the STAC Auth Proxy, which provides authentication and authorization for STAC APIs.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- An OIDC provider (e.g., Auth0, Cognito, Keycloak)
- A STAC API endpoint

## Installation

### Add the Helm Repository

```bash
helm registry login ghcr.io
helm pull oci://ghcr.io/developmentseed/stac-auth-proxy/charts/stac-auth-proxy --version 0.1.0
```

### Install the Chart

Basic installation with minimal configuration:

```bash
helm install stac-auth-proxy oci://ghcr.io/developmentseed/stac-auth-proxy/charts/stac-auth-proxy \
  --set env.UPSTREAM_URL=https://your-stac-api.com/stac \
  --set env.OIDC_DISCOVERY_URL=https://your-auth-server/.well-known/openid-configuration \
  --set ingress.host=stac-proxy.your-domain.com
```

### Using a Values File

Create a `values.yaml` file:

```yaml
env:
  UPSTREAM_URL: "https://your-stac-api.com/stac"
  OIDC_DISCOVERY_URL: "https://your-auth-server/.well-known/openid-configuration"
  OIDC_DISCOVERY_INTERNAL_URL: "http://auth-server-internal/.well-known/openid-configuration"
  DEFAULT_PUBLIC: "false"
  HEALTHZ_PREFIX: "/healthz"

ingress:
  enabled: true
  host: "stac-proxy.your-domain.com"
  tls:
    enabled: true

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 200m
    memory: 256Mi
```

Install using the values file:

```bash
helm install stac-auth-proxy oci://ghcr.io/developmentseed/stac-auth-proxy/charts/stac-auth-proxy -f values.yaml
```

### Using Image Pull Secrets

To use private container registries, you can configure image pull secrets:

```yaml

serviceAccount:
    create: true
    imagePullSecrets:
        name: "my-registry-secret"
```


## Configuration

### Required Values

| Parameter | Description |
|-----------|-------------|
| `env.UPSTREAM_URL` | URL of the STAC API to proxy |
| `env.OIDC_DISCOVERY_URL` | OpenID Connect discovery document URL |

### Optional Values

| Parameter | Description | Default |
|-----------|-------------|---------|
| `env` | Environment variables passed to the container. See [STAC Auth Proxy documentation](https://github.com/developmentseed/stac-auth-proxy#configuration) for details | `{}` |
| `ingress.enabled` | Enable ingress | `true` |
| `ingress.className` | Ingress class name | `nginx` |
| `ingress.host` | Hostname for the ingress | `""` |
| `ingress.tls.enabled` | Enable TLS for ingress | `true` |
| `replicaCount` | Number of replicas | `1` |

For a complete list of values, see the [values.yaml](./values.yaml) file.

## Upgrading

To upgrade the release:

```bash
helm upgrade stac-auth-proxy oci://ghcr.io/developmentseed/stac-auth-proxy/charts/stac-auth-proxy -f values.yaml
```

## Uninstalling

To uninstall/delete the deployment:

```bash
helm uninstall stac-auth-proxy
```

## Development

To test the chart locally:

```bash
helm install stac-auth-proxy ./helm --dry-run --debug
```

## Support

For support, please open an issue in the [STAC Auth Proxy repository](https://github.com/developmentseed/stac-auth-proxy/issues). 