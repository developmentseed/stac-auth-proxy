# Getting Started

STAC Auth Proxy is a reverse proxy that adds authentication and authorization to your STAC API. It sits between clients and your STAC API, validating tokens to authenticate request and applying custom authorization rules.

## Core Requirements

To get started with STAC Auth Proxy, you need to provide two essential pieces of information:

### 1. OIDC Discovery URL

You need a valid OpenID Connect (OIDC) discovery URL that points to your identity provider's configuration. This URL typically follows the pattern:

```
https://your-auth-provider.com/.well-known/openid-configuration
```

> [!TIP]
>
> Common OIDC providers include:
>
> - **Auth0**: `https://{tenant-id}.auth0.com/.well-known/openid-configuration`
> - **AWS Cognito**: `https://cognito-idp.{region}.amazonaws.com/{user-pool-id}/.well-known/openid-configuration`
> - **Azure AD**: `https://login.microsoftonline.com/{tenant-id}/v2.0/.well-known/openid-configuration`
> - **Google**: `https://accounts.google.com/.well-known/openid-configuration`
> - **Keycloak**: `https://{keycloak-server}/auth/realms/{realm-id}/.well-known/openid-configuration`

### 2. Upstream STAC API URL

You need the URL to your upstream STAC API that the proxy will protect:

```
https://your-stac-api.com/stac
```

This should be a valid STAC API that conforms to the STAC specification.

## Quick Start

Here's a minimal example to get you started:

### Using Docker

```bash
docker run -p 8000:8000 \
  -e UPSTREAM_URL=https://your-stac-api.com/stac \
  -e OIDC_DISCOVERY_URL=https://your-auth-provider.com/.well-known/openid-configuration \
  ghcr.io/developmentseed/stac-auth-proxy:latest
```

### Using Python

1. Install the package:
   ```bash
   pip install stac-auth-proxy
   ```
2. Set environment variables:
   ```bash
   export UPSTREAM_URL=https://your-stac-api.com/stac
   export OIDC_DISCOVERY_URL=https://your-auth-provider.com/.well-known/openid-configuration
   ```
3. Run the proxy:
   ```bash
   python -m stac_auth_proxy
   ```

### Using Docker Compose

For development and experimentation, the codebase (ie within the repository, not within the Docker or Python distributions) ships with a `docker-compose.yaml` file, allowing the proxy to be run locally alongside various supporting services: the database, the STAC API, and a Mock OIDC provider.

#### pgSTAC Backend

Run the application stack with a pgSTAC backend using [stac-fastapi-pgstac](https://github.com/stac-utils/stac-fastapi-pgstac):

```sh
docker compose up
```

#### OpenSearch Backend

Run the application stack with an OpenSearch backend using [stac-fastapi-elasticsearch-opensearch](https://github.com/stac-utils/stac-fastapi-elasticsearch-opensearch):

```sh
docker compose --profile os up
```

The proxy will start on `http://localhost:8000` by default.

## What Happens Next?

Once the proxy starts successfully:

1. **Health Check**: The proxy verifies your upstream STAC API is accessible
2. **Conformance Check**: It ensures your STAC API conforms to required specifications
3. **OIDC Discovery**: It fetches and validates your OIDC provider configuration
4. **Ready**: The proxy is now ready to handle requests

## Testing Your Setup

You can test that your proxy is working by accessing the health endpoint:

```bash
curl http://localhost:8000/healthz
```

## Next Steps

- [Configuration Guide](configuration.md) - Learn about all available configuration options
- [Route-Level Authentication](route-level-auth.md) - Configure which endpoints require authentication
- [Record-Level Authentication](record-level-auth.md) - Set up content filtering based on user permissions
