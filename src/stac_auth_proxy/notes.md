# Demo Video

1. Setup `.env`:

```sh
# Basic Setup
UPSTREAM_URL=http://stac:8001
OIDC_DISCOVERY_URL=http://localhost:8888/.well-known/openid-configuration
OIDC_DISCOVERY_INTERNAL_URL=http://oidc:8888/.well-known/openid-configuration

# Augmenting OpenAPI Spec
OPENAPI_SPEC_ENDPOINT=/api

# Adding new public endpoint
PUBLIC_ENDPOINTS={"^/api.html$": ["GET"], "^/api$": ["GET"], "^/docs/oauth2-redirect": ["GET"], "^/healthz": ["GET"], "^/_mgmt/.*": ["GET"]}

# Specifying required scope 
PRIVATE_ENDPOINTS={"^/collections$": [["POST", "collection:create"]]}

ITEMS_FILTER={"cls": "stac_auth_proxy.filters.Template", "args": ["{{ \"1=1\" if payload else \"properties.naip:year='2022'\" }}"]}

# 
SIGNER_ENDPOINT=/s3-signing
SIGNER_ASSET_EXPRESSION=^https://naipeuwest.blob.core.windows.net/.*
```

1. Basic setup (upstream api + auth)
   1. run proxy with upstream api + auth
   2. demo protected endpoints, public endpoints (e.g. /healthz)
2. OpenAPI Augmentation
   1. set openapi path prefix to `stac-fastapi-pgstac` default of `/api`:
   ```sh
   OPENAPI_SPEC_ENDPOINT=/api
   ```
   2. restart server:
   ```sh
   docker compose up -d --force-recreate --no-deps proxy
   ```
   3. demo openapi swagger ui
3. Authentication Extension
4. Filtering
   1. set items filter:
   ```sh
   ITEMS_FILTER={"cls": "stac_auth_proxy.filters.Template", "args": ["{{ \"1=1\" if payload else \"properties.naip:year='2022'\" }}"]}
   ```
   2. restart server:
   ```sh
   docker compose up -d --force-recreate --no-deps proxy
   ```
   3. demo cql2 swagger ui

# pgSTAC Demo

1. Queryables
2. Validation of filtering

Current state of `stac-fastapi-pgstac` is that filtering is _not_ working on the `items` endpoint:

```sh
curl -s "http://localhost:8001/collections/naip/items?filter=\"naip:year\"='2022'" | jq '.features[].properties["naip:year"]'
"2023"
"2023"
"2023"
"2023"
"2023"
"2023"
"2023"
"2023"
"2023"
"2023"
```

BUG: Why is upstream STAC API encoding response when we didn't send an accept-encoding header?

- [Filters extension](https://github.com/stac-api-extensions/filter) - declares format of filter
- [`Features Filter` conformance class](http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/features-filter) - Filter applied to features list endpoint
- [`Item Search`](https://github.com/radiantearth/stac-api-spec/tree/release/v1.0.0/item-search#stac-api---item-search)
- [`Collection Search`](https://github.com/stac-api-extensions/collection-search)

> [!TODO] Chat with Emmanuel about filtering the items features list endpoint.

If we want to support filtering on the items endpoint, we could instead use the `Item Search` extension.

Alternatively, we could manually filter response body to remove any STAC collections/items that don't match cql2 expression.

---

Conformance check:

When you spin up the proxy, it should check the upstream API and validate that it conforms to expected configuration (e.g. has item search, maybe has collections search).
