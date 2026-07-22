"""Optional Prometheus metrics for STAC operations."""

import re
from typing import Any, Callable, Optional

METRICS_AVAILABLE = False
Instrumentator: Any = None
stac_operation_instrumentation: Optional[Callable[[Any], None]] = None

OPERATIONS = [  # ordered; first match wins
    (r"^/$", {"GET": "landing_page"}),
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
    (r"^/collections/[^/]+/bulk_items$", {"POST": "bulk_create_items"}),
]
_COMPILED = [(re.compile(p), m) for p, m in OPERATIONS]


def classify_operation(method: str, path: str) -> str:
    """Map a request to a low-cardinality STAC operation name."""
    for pattern, methods in _COMPILED:
        if pattern.match(path):
            return methods.get(method.upper(), "other")
    return "other"


try:
    from prometheus_client import Histogram
    from prometheus_fastapi_instrumentator import Instrumentator as _Instrumentator
    from prometheus_fastapi_instrumentator.metrics import Info

    _DURATION = Histogram(
        "stac_operation_duration_seconds",
        "Request duration by STAC operation.",
        labelnames=("operation", "status"),
    )

    def _stac_operation_instrumentation(info: Info) -> None:
        """Observe request duration labeled by STAC operation."""
        _DURATION.labels(
            operation=classify_operation(info.request.method, info.request.url.path),
            status=info.modified_status,
        ).observe(info.modified_duration)

    Instrumentator = _Instrumentator
    stac_operation_instrumentation = _stac_operation_instrumentation
    METRICS_AVAILABLE = True

except ImportError:
    pass
