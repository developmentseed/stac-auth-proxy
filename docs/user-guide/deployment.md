# Deployment

## General

Deploying the STAC Auth Proxy is similar to deploying any other service. In general, we recommend you mirror the architecture of your other systems.

The core principles of deploying the STAC Auth Proxy are:

1. The STAC API should not be available on the public internet
2. The STAC Auth Proxy should be able to communicate with both the STAC API and the OIDC Server (namely, the discovery endpoint and JWKS endpoint)

### Networking Considerations

#### Hiding the STAC API

The STAC API should not be directly accessible from the public internet. The STAC Auth Proxy acts as the public-facing endpoint.

##### AWS Strategy

- Place the STAC API in a private subnet
- Place the STAC Auth Proxy in a public subnet with internet access
- Use security groups to restrict access between components

##### Kubernetes Strategy

- Deploy the STAC API as an internal service (ClusterIP)
- Deploy the STAC Auth Proxy with an Ingress for external access
- Use network policies to control traffic flow

#### Communicating with the OIDC Server

The STAC Auth Proxy needs to communicate with your OIDC provider for authentication. If your OIDC server is not directly available to the STAC Auth Proxy, use [`OIDC_DISCOVERY_INTERNAL_URL`](configuration.md#oidc_discovery_internal_url) (the [`OIDC_DISCOVERY_URL`](configuration.md#oidc_discovery_url) will still be used for auth in the browser, such as the Swagger UI page).

## AWS Lambda

For AWS Lambda deployments, we recommend using the [Mangum](https://pypi.org/project/mangum/) handler with disabled lifespan events. Such a handler is available at `stac_auth_proxy.lambda:handler`.

> [!TIP]
>
> If using `stac_auth_proxy.lambda:handler`, be sure to install the `lambda` optional dependencies:
>
> ```bash
> pip install stac_auth_proxy[lambda]
> ```

### CDK

If using [AWS CDK](https://docs.aws.amazon.com/cdk/), a [`StacAuthProxy` Construct](https://developmentseed.org/eoapi-cdk/#stacauthproxylambda-) is made available within the [`eoapi-cdk`](https://github.com/developmentseed/eoapi-cdk) project.

## Docker

The STAC Auth Proxy is available as a [Docker image from the GitHub Container Registry (GHCR)](https://github.com/developmentseed/stac-auth-proxy/pkgs/container/stac-auth-proxy).

```bash
# Latest version
docker pull ghcr.io/developmentseed/stac-auth-proxy:latest

# Specific version
docker pull ghcr.io/developmentseed/stac-auth-proxy:v0.7.1
```

## Kubernetes

The STAC Auth Proxy can be deployed to Kubernetes via the [Helm Chart available on the GitHub Container Registry (GHCR)](https://github.com/developmentseed/stac-auth-proxy/pkgs/container/stac-auth-proxy%2Fcharts%2Fstac-auth-proxy).

### Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+

### Installation

```bash
# Add the Helm repository
helm registry login ghcr.io

# Install with minimal configuration
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

### Management

```bash
# Upgrade
helm upgrade stac-auth-proxy oci://ghcr.io/developmentseed/stac-auth-proxy/charts/stac-auth-proxy

# Uninstall
helm uninstall stac-auth-proxy
```
