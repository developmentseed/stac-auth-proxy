# Record-Level Authorization

Record-level authorization (also known as _row-level_ authorization) provides fine-grained access control to individual STAC records (items and collections) based on user and request context. This ensures users only see data they're authorized to access, regardless of their authentication status.

> [!IMPORTANT]
>
> The upstream STAC API must support the [STAC API Filter Extension](https://github.com/stac-api-extensions/filter/blob/main/README.md), including the [Features Filter](http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/features-filter) conformance class on the Features resource (`/collections/{cid}/items`).

## How It Works

Record-level authorization is implemented through **data filtering**—a strategy that generates CQL2 filters based on request context and applies them to outgoing requests before they reach the upstream STAC API. This approach ensures that:

- Users only see records they're authorized to access
- Unauthorized records are completely hidden from search results
- Authorization decisions are made at the database level for optimal performance
- Access control is enforced consistently across all endpoints

For endpoints where the filter extension doesn't apply (such as single-item endpoints), the filters are used to validate response data from the upstream STAC API before the user receives the data, ensuring complete authorization coverage.

> [!NOTE]
>
> For more information on _how_ data filtering works, some more information can be found in the [architecture section](../architecture/filtering-data.md) of the docs.

## Supported Operations

### Collection-Level Filtering

The [`COLLECTIONS_FILTER_CLS`](configuration.md#collections_filter_cls) applies filters to the following operations:

**Currently Supported:**

- `GET /collections` - Append query params with generated CQL2 query
- `GET /collections/{collection_id}` - Validate response against CQL2 query

**Future Support:**

- `POST /collections/` - Validate body with generated CQL2 query[^22]
- `PUT /collections/{collection_id}` - Fetch and validate collection with CQL2 query[^22]
- `DELETE /collections/{collection_id}` - Fetch and validate collection with CQL2 query[^22]

### Item-Level Filtering

The [`ITEMS_FILTER_CLS`](configuration.md#items_filter_cls) applies filters to the following operations:

**Currently Supported:**

- `GET /search` - Append query params with generated CQL2 query
- `POST /search` - Append body with generated CQL2 query
- `GET /collections/{collection_id}/items` - Append query params with generated CQL2 query
- `GET /collections/{collection_id}/items/{item_id}` - Validate response against CQL2 query

**Future Support:**

- `POST /collections/{collection_id}/items` - Validate body with generated CQL2 query[^21]
- `PUT /collections/{collection_id}/items/{item_id}` - Fetch and validate item with CQL2 query[^21]
- `DELETE /collections/{collection_id}/items/{item_id}` - Fetch and validate item with CQL2 query[^21]
- `POST /collections/{collection_id}/bulk_items` - Validate items in body with generated CQL2 query[^21]

## Filter Contract

A filter factory implements the following contract:

- A class or function that may take initialization arguments
- Once initialized, the factory is a callable with the following behavior:
  - **Input**: A context dictionary containing request and user information
  - **Output**: A valid CQL2 expression (as a string or dict) that filters the data

In Python typing syntax, it conforms to:

```py
FilterFactory = Callable[..., Callable[[dict[str, Any]], Awaitable[str | dict[str, Any]]]]
```

### Example Filter Factory

```py
import dataclasses
from typing import Any


@dataclasses.dataclass
class ExampleFilter:
    async def __call__(self, context: dict[str, Any]) -> str:
        return "true"
```

> [!TIP]
> Despite being referred to as a _class_ in the settings, a filter factory could be written as a function.
>
>   <details>
>
>   <summary>Example</summary>
>
> ```py
> from typing import Any
>
>
> def example_filter():
>     async def example_filter(context: dict[str, Any]) -> str | dict[str, Any]:
>         return "true"
>     return example_filter
> ```
>
> </details>

### Context Structure

The context contains request and user information:

```python
{
    "req": {
        "path": "/collections/landsat-8/items",
        "method": "GET",
        "query_params": {"limit": "10"},
        "path_params": {"collection_id": "landsat-8"},
        "headers": {"authorization": "Bearer ..."}
    },
    "payload": {
        "sub": "user123",
        "scope": "profile email admin",
        "iss": "https://auth.example.com"
    }
}
```

## Filters Configuration

Configure filters using environment variables:

```bash
# Basic configuration
ITEMS_FILTER_CLS=stac_auth_proxy.filters:Template
ITEMS_FILTER_ARGS='["collection IN ('public')"]'

# With keyword arguments
ITEMS_FILTER_CLS=stac_auth_proxy.filters:Opa
ITEMS_FILTER_ARGS='["http://opa:8181", "stac/items/allow"]'
ITEMS_FILTER_KWARGS='{"cache_ttl": 30.0}'
```

**Environment Variables:**

- `{FILTER_TYPE}_FILTER_CLS`: The class path
- `{FILTER_TYPE}_FILTER_ARGS`: Positional arguments (comma-separated)
- `{FILTER_TYPE}_FILTER_KWARGS`: Keyword arguments (comma-separated key=value pairs)

## Built-in Filter Factorys

### Template Filter

Generate CQL2 expressions using the [Jinja](https://jinja.palletsprojects.com/en/stable/) templating engine. Given the request context, the Jinja template expression should render a valid CQL2 expression (likely in `cql2-text` format).

```bash
ITEMS_FILTER_CLS=stac_auth_proxy.filters:Template
ITEMS_FILTER_ARGS='["{{ \"true\" if payload else \"(preview IS NULL) OR (preview = false)\" }}"]'
```

> [!TIP]
>
> The Template Filter works well for situations where the filter logic does not need to change, such as simply translating a property from a JWT to a CQL2 expression.

### OPA Filter

Delegate authorization to [Open Policy Agent](https://www.openpolicyagent.org/). For each request, we call out to an OPA decision with the request context, expecting that OPA will return a valid CQL2 expression.

```bash
ITEMS_FILTER_CLS=stac_auth_proxy.filters:opa.Opa
ITEMS_FILTER_ARGS='["http://opa:8181","stac/items_cql2"]'
```

**OPA Policy Example:**

```rego
package stac

# Anonymous users only see NAIP collection
default collections_cql2 := "id = 'naip'"

collections_cql2 := "true" if {
    # Authenticated users get all collections
	input.payload.sub != null
}

# Anonymous users only see NAIP year 2021 data
default items_cql2 := "\"naip:year\" = 2021"

items_cql2 := "true" if {
    # Authenticated users get all items
	input.payload.sub != null
}
```

## Custom Filter Factories

> [!TIP]
> An example integration can be found in [`examples/custom-integration`](https://github.com/developmentseed/stac-auth-proxy/blob/main/examples/custom-integration).

### Complex Filter Factory

An example of a more complex filter factory where the filter is generated based on the response of an external API:

```py
import dataclasses
from typing import Any, Literal, Optional

from httpx import AsyncClient
from stac_auth_proxy.utils.cache import MemoryCache


@dataclasses.dataclass
class ApprovedCollectionsFilter:
    api_url: str
    kind: Literal["item", "collection"] = "item"
    client: AsyncClient = dataclasses.field(init=False)
    cache: MemoryCache = dataclasses.field(init=False)

    def __post_init__(self):
        # We keep the client in the class instance to avoid creating a new client for
        # each request, taking advantage of the client's connection pooling.
        self.client = AsyncClient(base_url=self.api_url)
        self.cache = MemoryCache(ttl=30)

    async def __call__(self, context: dict[str, Any]) -> dict[str, Any]:
        token = context["req"]["headers"].get("authorization")

        try:
            # Check cache for a previously generated filter
            approved_collections = self.cache[token]
        except KeyError:
            # Look up approved collections from an external API
            approved_collections = await self.lookup(token)
            self.cache[token] = approved_collections

        # Build CQL2 filter
        return {
            "op": "a_containedby",
            "args": [
                {"property": "collection" if self.kind == "item" else "id"},
                approved_collections
            ],
        }

    async def lookup(self, token: Optional[str]) -> list[str]:
        # Look up approved collections from an external API
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = await self.client.get(
            f"/get-approved-collections",
            headers=headers,
        )
        response.raise_for_status()
        return response.json()["collections"]
```

> [!TIP]
> Filter generation runs for every relevant request. Consider memoizing external API calls to improve performance.

[^21]: https://github.com/developmentseed/stac-auth-proxy/issues/21
[^22]: https://github.com/developmentseed/stac-auth-proxy/issues/22
