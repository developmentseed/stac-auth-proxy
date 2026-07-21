# STAC Auth Proxy Helm Chart

For documentation, see [Kubernetes Deployment](https://developmentseed.org/stac-auth-proxy/user-guide/deployment/).

## Local Installation

```bash
helm install stac-auth-proxy ./helm
```

## Probes and `ROOT_PATH`

Startup, liveness, and readiness probes default `httpGet.path` to `{env.ROOT_PATH}{env.HEALTHZ_PREFIX}` (e.g. `/stac/healthz` when `ROOT_PATH=/stac`). If unset, that is `/healthz`. Set `startupProbe` / `livenessProbe` / `readinessProbe` `httpGet.path` explicitly to override.
