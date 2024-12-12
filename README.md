# STAC Auth Proxy

> [!WARNING]
> This project is currently in active development and may change drastically in the near future while we work towards solidifying a first release.

STAC Auth Proxy is a proxy API that mediates between the client and and some internally accessible STAC API in order to provide a flexible authentication mechanism.

## Features

- 🔐 Selectively apply OIDC auth to some or all endpoints & methods
- 📖 Augments [OpenAPI](https://swagger.io/specification/) with auth information, keeping auto-generated docs (e.g. [Swagger UI](https://swagger.io/tools/swagger-ui/)) accurate

## Installation

Set up connection to upstream STAC API and the OpenID Connect provider by setting the following environment variables:

```bash
export STAC_AUTH_PROXY_UPSTREAM_URL="https://some.url"
export STAC_AUTH_PROXY_OIDC_DISCOVERY_URL="https://your-openid-connect-provider.com/.well-known/openid-configuration"
```

Install software:

```bash
uv run python -m stac_auth_proxy
```
