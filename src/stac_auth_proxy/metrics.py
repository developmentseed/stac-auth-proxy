"""Optional Prometheus metrics for STAC operations."""

import re
from typing import Any, Optional, Sequence

METRICS_AVAILABLE = False

OPERATIONS = [  # ordered; first match wins
    (r"^/$", {"GET": "landing"}),
    (r"^/conformance$", {"GET": "conformance"}),
    (r"^/search$", {"GET": "search", "POST": "search"}),
    (r"^/collections$", {"GET": "list_collections", "POST": "create_collection"}),
    (
        r"^/collections/[^/]+$",
        {
            "GET": "get_collection",
            "PUT": "edit_collection",
            "PATCH": "edit_collection",
            "DELETE": "delete_collection",
        },
    ),
    (r"^/collections/[^/]+/items$", {"GET": "list_items", "POST": "create_item"}),
    (
        r"^/collections/[^/]+/items/[^/]+$",
        {
            "GET": "get_item",
            "PUT": "edit_item",
            "PATCH": "edit_item",
            "DELETE": "delete_item",
        },
    ),
    (r"^/collections/[^/]+/bulk_items$", {"POST": "bulk"}),
]
_COMPILED = [(re.compile(p), m) for p, m in OPERATIONS]


def classify_operation(method: str, path: str) -> str:
    """Map a request to a low-cardinality STAC operation name."""
    for pattern, methods in _COMPILED:
        if pattern.match(path):
            return methods.get(method.upper(), "unknown")
    return "unknown"


def instrument_app(
    app: Any,
    excluded_handlers: Optional[Sequence[str]] = None,
) -> None:
    """Instrument a FastAPI app and expose Prometheus metrics when available."""
    if not METRICS_AVAILABLE:
        return
    _instrument_app(app, list(excluded_handlers or []))


try:
    from prometheus_client import Counter, Histogram
    from prometheus_fastapi_instrumentator import Instrumentator
    from prometheus_fastapi_instrumentator.metrics import Info

    REQUESTS = Counter(
        "http_requests_total",
        "Total HTTP requests by STAC operation.",
        labelnames=("operation", "method", "status"),
    )
    LATENCY = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency by STAC operation.",
        labelnames=("operation", "method"),
        buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, float("inf")),
    )

    def record_stac_metrics(info: Info) -> None:
        """Record request count and latency using STAC operation labels."""
        operation = classify_operation(info.request.method, info.request.url.path)
        REQUESTS.labels(operation, info.method, info.modified_status).inc()
        LATENCY.labels(operation, info.method).observe(info.modified_duration)

    def _instrument_app(app: Any, excluded_handlers: list[str]) -> None:
        (
            Instrumentator(
                should_group_status_codes=True,
                excluded_handlers=excluded_handlers,
            )
            .add(record_stac_metrics)
            .instrument(app)
            .expose(app, endpoint="/_mgmt/metrics", include_in_schema=False)
        )

    METRICS_AVAILABLE = True

except ImportError:

    def _instrument_app(app: Any, excluded_handlers: list[str]) -> None:
        return
