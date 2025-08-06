# Filtering Data

> [!NOTE]
>
> For more information on using filters to solve authorization needs, more information can be found in the [user guide](../user-guide/record-level-auth.md).

## Example Request Flow for multi-record endpoints

```mermaid
sequenceDiagram
    Client->>Proxy: GET /collections
    Note over Proxy: EnforceAuth checks credentials
    Note over Proxy: BuildCql2Filter creates filter
    Note over Proxy: ApplyCql2Filter applies filter to request
    Proxy->>STAC API: GET /collection?filter=(collection=landsat)
    STAC API->>Client: Response
```

## Example Request Flow for single-record endpoints

The Filter Extension does not apply to fetching individual records. As such, we must validate the record _after_ it is returned from the upstream API but _before_ it is returned to the user:

```mermaid
sequenceDiagram
    Client->>Proxy: GET /collections/abc123
    Note over Proxy: EnforceAuth checks credentials
    Note over Proxy: BuildCql2Filter creates filter
    Proxy->>STAC API: GET /collection/abc123
    Note over Proxy: ApplyCql2Filter validates the response
    STAC API->>Client: Response
```
