# Open Policy Agent (OPA) Integration

This example demonstrates how to integrate with an Open Policy Agent (OPA) to authorize requests to a STAC API.

## Running the Example

From the root directory, run:

```sh
docker compose -f docker-compose.yaml -f examples/opa/docker-compose.yaml up
```

## Testing OPA

```sh
▶ curl -X POST "http://localhost:8181/v1/data/stac/cql2" \
  -H "Content-Type: application/json" \
  -d '{"input":{"payload": null}}'
{"result":"private = true"}
```

```sh
▶ curl -X POST "http://localhost:8181/v1/data/stac/cql2" \
  -H "Content-Type: application/json" \
  -d '{"input":{"payload": {"sub": "user1"}}}'
{"result":"1=1"}
```
