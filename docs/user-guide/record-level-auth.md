# Record-Level Authorization

Record-level authorization (also known as _row-level_ authorization) provides fine-grained access control to individual STAC records (items and collections) based on user and request context. This ensures users only see data they're authorized to access, regardless of their authentication status.

> [!IMPORTANT]
>
> The upstream STAC API must support the [STAC API Filter Extension](https://github.com/stac-api-extensions/filter/blob/main/README.md), including the [Features Filter](http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/features-filter) conformance class on the Features resource (`/collections/{cid}/items`).

## How It Works

Record-level authorization is implemented through **data filtering**—a strategy that generates CQL2 filters based on request context and applies them to requests. This approach ensures that:

- Users only see records they're authorized to access
- Unauthorized records are completely hidden from search results
- Users can only create, update, or delete records that match their access filter
- Authorization decisions are made at the database level for optimal performance
- Access control is enforced consistently across all endpoints

For **read** operations on list endpoints, the CQL2 filter is appended to the outgoing request so filtering happens at the database level. For single-resource read endpoints, the filter validates the upstream response before the user receives it. For **write** operations (create, update, delete), the filter validates the request body and/or existing record to ensure the user is authorized to modify the resource.

> [!NOTE]
>
> For more information on _how_ data filtering works, some more information can be found in the [architecture section](../architecture/filtering-data.md) of the docs.

## Supported Operations

### Collection-Level Filtering

The [`COLLECTIONS_FILTER_CLS`](configuration.md#collections_filter_cls) applies filters to the following operations:

- `GET /collections` - Append query params with generated CQL2 query
- `GET /collections/{collection_id}` - Validate response against CQL2 query
- `POST /collections` - Validate request body against CQL2 query
- `PUT /collections/{collection_id}` - Fetch existing collection, validate both existing and new body against CQL2 query
- `PATCH /collections/{collection_id}` - Fetch existing collection, validate both existing and merged result against CQL2 query
- `DELETE /collections/{collection_id}` - Fetch existing collection, validate against CQL2 query

### Item-Level Filtering

The [`ITEMS_FILTER_CLS`](configuration.md#items_filter_cls) applies filters to the following operations:

- `GET /search` - Append query params with generated CQL2 query
- `POST /search` - Append body with generated CQL2 query
- `GET /collections/{collection_id}/items` - Append query params with generated CQL2 query
- `GET /collections/{collection_id}/items/{item_id}` - Validate response against CQL2 query
- `POST /collections/{collection_id}/items` - Validate request body against CQL2 query
- `POST /collections/{collection_id}/bulk_items` - Validate items in body with generated CQL2 query
- `PUT /collections/{collection_id}/items/{item_id}` - Fetch existing item, validate both existing and new body against CQL2 query
- `PATCH /collections/{collection_id}/items/{item_id}` - Fetch existing item, validate both existing and merged result against CQL2 query
- `DELETE /collections/{collection_id}/items/{item_id}` - Fetch existing item, validate against CQL2 query

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
ITEMS_FILTER_ARGS=["collection IN ('public')"]

# With keyword arguments
ITEMS_FILTER_CLS=stac_auth_proxy.filters:Opa
ITEMS_FILTER_ARGS=["http://opa:8181", "stac/items/allow"]
ITEMS_FILTER_KWARGS={"cache_ttl": 30.0}
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

### Creating Filter Factories

A single filter factory (e.g., `ITEMS_FILTER_CLS`) is called across many different endpoints and HTTP methods. The same filter is used for read operations (`GET /search`, `GET /collections/{cid}/items`), single-resource reads (`GET /collections/{cid}/items/{iid}`), and write operations (`POST`, `PUT`, `PATCH`, `DELETE`). This means your filter factory may need to return different CQL2 expressions depending on the request.

For example, you might want to allow all authenticated users to _read_ items but restrict _writes_ to items belonging to their organization:

```py
import dataclasses
from typing import Any


@dataclasses.dataclass
class ItemsFilter:
    async def __call__(self, context: dict[str, Any]) -> dict[str, Any] | str:
        method = context["req"]["method"]
        path = context["req"]["path"]

        # Read operations: GET requests and POST /search
        if method == "GET" or path.endswith("/search"):
            return "1=1"

        # Write operations: restrict to user's organization
        org = context["payload"].get("org", "")
        return {
            "op": "=",
            "args": [{"property": "organization"}, org],
        }
```

The `context["req"]` dict gives you access to `path`, `method`, `query_params`, `path_params`, and `headers`, so you can tailor the filter to the specific operation. See [Context Structure](record-level-auth.md#context-structure) for the full structure.

### Security

When building CQL2 filters from user-controlled values (JWT claims, query parameters, headers), avoid string interpolation. A malicious claim value could break out of the intended expression, similar to SQL injection. For example, this is **unsafe**:

```py
# UNSAFE: vulnerable to CQL2 injection
org = context["payload"].get("org", "")
return f"organization = '{org}'"
```

A payload like `{"org": "' OR 1=1"}` would produce a CQL2 expression of `organization = '' OR 1=1` which reduces to `true`, thereby giving the user full access to possibly-sensitive data.

Instead, return CQL2-JSON (a dict). Values are passed as data rather than embedded in a parsed expression, which eliminates injection risk:

```py
# Safe: values are data, not part of a parsed expression
org = context["payload"].get("org", "")
return {
    "op": "=",
    "args": [{"property": "organization"}, org],
}
```

> [!NOTE]
> The `Cql2BuildFilterMiddleware` accepts both CQL2-text (string) and CQL2-JSON (dict) from filter factories. Both formats are parsed via `cql2.Expr()` and validated with `expr.validate()`. Downstream middleware then automatically converts the expression to the appropriate format based on the request type: **GET requests** receive CQL2-text (via `Expr.to_text()`), while **POST requests** receive CQL2-JSON (via `Expr.to_json()`). This means returning CQL2-JSON from your filter factory gives you injection safety with no loss of compatibility.

If you must return a CQL2-text string, validate and sanitize the value first:

```py
import re

org = context["payload"].get("org", "")
if not re.match(r"^[a-zA-Z0-9_-]+$", org):
    raise ValueError(f"Invalid organization: {org}")
return f"organization = '{org}'"
```

### Testing Filter Factories

You can test filter factories with [pytest](https://docs.pytest.org/) and the [`cql2`](https://pypi.org/project/cql2/) library's [`Expr.matches()` method](https://developmentseed.org/cql2-rs/latest/python/#cql2.Expr.matches). `Expr.matches()` evaluates a CQL2 expression against a record dict, which lets you verify that your filter allows and denies the correct records without needing a running STAC API.

```py
import pytest
from cql2 import Expr

from my_filters import ItemsFilter


@pytest.fixture
def items_filter():
    return ItemsFilter()


@pytest.mark.asyncio
async def test_read_allows_all_items(items_filter):
    """GET requests should return a permissive filter."""
    cql2 = await items_filter({
        "req": {
            "method": "GET",
            "path": "/search",
            "query_params": {},
            "path_params": {},
            "headers": {},
        },
        "payload": {},
    })
    expr = Expr(cql2)
    expr.validate()

    assert expr.matches({"organization": "org-a"})
    assert expr.matches({"organization": "org-b"})


@pytest.mark.asyncio
async def test_write_restricts_to_org(items_filter):
    """Write requests should only allow items matching the user's org."""
    cql2 = await items_filter({
        "req": {
            "method": "POST",
            "path": "/collections/test/items",
            "query_params": {},
            "path_params": {},
            "headers": {},
        },
        "payload": {"org": "org-a"},
    })
    expr = Expr(cql2)
    expr.validate()

    assert expr.matches({"organization": "org-a"})
    assert not expr.matches({"organization": "org-b"})
```

This pattern lets you verify two things independently:

1. **Filter generation** — does your factory produce the right CQL2 expression for a given context?
2. **Filter correctness** — does that CQL2 expression match (and reject) the expected records?

### Complex Filter Factory

> [!TIP]
> An example integration can be found in [`examples/custom-integration`](https://github.com/developmentseed/stac-auth-proxy/blob/main/examples/custom-integration).

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

