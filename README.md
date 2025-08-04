<div align="center">
  <h1 style="font-family: monospace">stac auth proxy</h1>
  <p align="center">Reverse proxy to apply auth*n to your STAC API.</p>
</div>

---

[![PyPI - Version][pypi-version-badge]][pypi-link]
[![GHCR - Version][ghcr-version-badge]][ghcr-link]
[![GHCR - Size][ghcr-size-badge]][ghcr-link]

STAC Auth Proxy is a proxy API that mediates between the client and your internally accessible STAC API to provide flexible authentication, authorization, and content-filtering mechanisms.

> [!IMPORTANT]
>
> **We would :heart: to hear from you!**
> Please [join the discussion](https://github.com/developmentseed/eoAPI/discussions/209) and let us know how you're using eoAPI! This helps us improve the project for you and others.
> If you prefer to remain anonymous, you can email us at eoapi@developmentseed.org, and we'll be happy to post a summary on your behalf.

## ✨Features✨

- **🔐 Authentication:** Apply [OpenID Connect (OIDC)](https://openid.net/developers/how-connect-works/) token validation and optional scope checks to specified endpoints and methods
- **🛂 Content Filtering:** Use CQL2 filters via the [Filter Extension](https://github.com/stac-api-extensions/filter?tab=readme-ov-file) to tailor API responses based on request context (e.g. user role)
- **🤝 External Policy Integration:** Integrate with external systems (e.g. [Open Policy Agent (OPA)](https://www.openpolicyagent.org/)) to generate CQL2 filters dynamically from policy decisions
- **🧩 Authentication Extension:** Add the [Authentication Extension](https://github.com/stac-extensions/authentication) to API responses to expose auth-related metadata
- **📘 OpenAPI Augmentation:** Enhance the [OpenAPI spec](https://swagger.io/specification/) with security details to keep auto-generated docs and UIs (e.g., [Swagger UI](https://swagger.io/tools/swagger-ui/)) accurate
- **🗜️ Response Compression:** Optimize response sizes using [`starlette-cramjam`](https://github.com/developmentseed/starlette-cramjam/)

## Documentation

[Full documentation is available on the website](https://developmentseed.org/stac-auth-proxy).

Head to [Getting Started](https://developmentseed.org/stac-auth-proxy/getting-started/) to dig in.

[pypi-version-badge]: https://badge.fury.io/py/stac-auth-proxy.svg
[pypi-link]: https://pypi.org/project/stac-auth-proxy/
[ghcr-version-badge]: https://ghcr-badge.egpl.dev/developmentseed/stac-auth-proxy/latest_tag?color=%2344cc11&ignore=latest&label=image+version&trim=
[ghcr-size-badge]: https://ghcr-badge.egpl.dev/developmentseed/stac-auth-proxy/size?color=%2344cc11&tag=latest&label=image+size&trim=
[ghcr-link]: https://github.com/developmentseed/stac-auth-proxy/pkgs/container/stac-auth-proxy
