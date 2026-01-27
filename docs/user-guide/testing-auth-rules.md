# Testing Auth Rules

The `stac-auth-tests` CLI tool validates your custom filter classes by running them in the same environment as production, ensuring your authorization rules work as expected.

## Overview

Run sanity checks on your auth filters within your production environment (Docker containers, kubernetes pods, etc.) to:

- **Validate filter logic** - Ensure filters generate correct CQL2 expressions and match items as expected
- **Catch regressions** - Verify changes don't break expected behavior before deployment
- **Test with production data** - Run filters against real STAC APIs and databases in your stack

## Test File Format

Test files use YAML (recommended) or JSON. Each test case contains:
- **context** - Request and JWT payload passed to your filter
- **tests** - Tuples of `[item, expected_match]` to validate

### Example Test File

```yaml
# tests/auth_rules.yaml
# Define reusable items with YAML anchors
items:
  public_item: &public_item
    id: item-1
    type: Feature
    collection: my-collection
    properties:
      private: false
    geometry: null

  private_item: &private_item
    id: item-2
    type: Feature
    collection: my-collection
    properties:
      private: true
    geometry: null

# Define reusable contexts
contexts:
  anonymous: &anonymous
    req:
      path: /collections/my-collection/items
      method: GET
      headers: {}
      query_params: {}
      path_params: {}

  authenticated: &authenticated
    req:
      path: /collections/my-collection/items
      method: GET
      headers:
        authorization: Bearer token
      query_params: {}
      path_params: {}
    payload:
      sub: user123
      collections: ["my-collection"]

test_cases:
  - name: Anonymous users see only public items
    context: *anonymous
    tests:
      - [*public_item, true]
      - [*private_item, false]

  - name: Authenticated users see their collections
    context: *authenticated
    tests:
      - [*public_item, true]
      - [*private_item, true]
```

See `tests/example_auth_rules.yaml` for a complete example.

## Running Tests

### With Docker Compose (Local Development)

Add test files to your compose volumes:

```yaml
# docker-compose.yaml
services:
  proxy:
    volumes:
      - ./tests:/app/tests
```

Run tests in your stack:

```bash
# Start services
docker compose up -d

# Run tests (creates isolated container with access to your stack)
docker compose run --rm proxy stac-auth-tests \
  --filter-class "my_filters:ItemsFilter" \
  --test-file /app/tests/auth_rules.yaml
```

This approach:
- Tests against your actual upstream STAC API
- Runs filters that make API calls (e.g., fetching public collections)
- Uses the same environment variables and network as production

### In Production Containers

```dockerfile
FROM ghcr.io/developmentseed/stac-auth-proxy:latest
COPY ./my_filters.py /app/my_filters.py
COPY ./tests /app/tests
```

```bash
# Build and test
docker build -t my-stac-proxy .
docker run --rm \
  -e UPSTREAM_URL=http://stac-api:8080 \
  my-stac-proxy \
  stac-auth-tests \
    --filter-class "my_filters:ItemsFilter" \
    --test-file /app/tests/auth_rules.yaml
```

### Locally (Development)

```bash
pip install -e .

stac-auth-tests \
  --filter-class "stac_auth_proxy.filters:Template" \
  --filter-args '["(properties.private = false)"]' \
  --test-file tests/auth_rules.yaml
```

## CLI Options

```bash
stac-auth-tests \
  --filter-class "module.path:ClassName"  # Required: filter class to test
  --filter-args '[...]'                   # Optional: JSON array of positional args
  --filter-kwargs '{...}'                 # Optional: JSON object of keyword args
  --test-file path/to/tests.yaml          # Required: test file path
```

## Example: Testing Custom Filter

```python
# my_filters.py
import dataclasses
from typing import Any

@dataclasses.dataclass
class ItemsFilter:
    collections_claim: str = "collections"

    async def __call__(self, context: dict[str, Any]) -> str:
        jwt = context.get("payload")
        if jwt:
            collections = jwt.get(self.collections_claim, [])
            return f"collection IN ({','.join(repr(c) for c in collections)})"
        return "(private IS NULL OR private = false)"
```

```yaml
# tests/my_tests.yaml
items:
  allowed: &allowed
    id: item-1
    collection: allowed-col
    type: Feature
    properties: {}
    geometry: null

  forbidden: &forbidden
    id: item-2
    collection: forbidden-col
    type: Feature
    properties: {}
    geometry: null

test_cases:
  - name: User with collection access
    context:
      req:
        path: /search
        method: POST
        headers:
          authorization: Bearer token
        query_params: {}
        path_params: {}
      payload:
        sub: user123
        collections: ["allowed-col"]
    tests:
      - [*allowed, true]
      - [*forbidden, false]
```

```bash
# Test it
docker compose run --rm proxy stac-auth-tests \
  --filter-class "my_filters:ItemsFilter" \
  --test-file /app/tests/my_tests.yaml
```

## CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Test Auth Rules

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build image
        run: docker build -t test-image .
      - name: Test auth rules
        run: |
          docker run --rm test-image \
            stac-auth-tests \
              --filter-class "my_filters:ItemsFilter" \
              --test-file /app/tests/auth_rules.yaml
```

## Troubleshooting

**"Failed to generate or validate CQL2 filter"**
- Your filter returned invalid CQL2 syntax
- Check that property references and operators are correct

**"Item match failures"**
- Filter is valid but items don't match as expected
- Verify property paths (e.g., `properties.private` vs `private`)
- Check data types match (strings vs booleans)

**"Error loading filter class"**
- Check class path format: `module.path:ClassName`
- Verify module is in Python path and dependencies are installed

## See Also

- [Record-Level Authorization Guide](record-level-auth.md)
- [CQL2 Specification](https://docs.ogc.org/DRAFTS/21-065.html)
