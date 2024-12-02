"""Pytest fixtures."""

import threading

import pytest
import uvicorn
from fastapi import FastAPI


@pytest.fixture(scope="session")
def source_api():
    """Create upstream API for testing purposes."""
    app = FastAPI(docs_url="/api.html", openapi_url="/api")

    for path, methods in {
        "/": ["GET"],
        "/conformance": ["GET"],
        "/queryables": ["GET"],
        "/search": ["GET", "POST"],
        "/collections": ["GET", "POST"],
        "/collections/{collection_id}": ["GET", "PUT", "DELETE"],
        "/collections/{collection_id}/items": ["GET", "POST"],
        "/collections/{collection_id}/items/{item_id}": [
            "GET",
            "PUT",
            "DELETE",
        ],
        "/collections/{collection_id}/bulk_items": ["POST"],
    }.items():
        for method in methods:
            # NOTE: declare routes per method separately to avoid warning of "Duplicate Operation ID ... for function <lambda>"
            app.add_api_route(
                path,
                lambda: {"id": f"Response from {method}@{path}"},
                methods=[method],
            )

    return app


@pytest.fixture(scope="session")
def source_api_server(source_api):
    """Run the source API in a background thread."""
    host, port = "127.0.0.1", 8000
    server = uvicorn.Server(
        uvicorn.Config(
            source_api,
            host=host,
            port=port,
        )
    )
    thread = threading.Thread(target=server.run)
    thread.start()
    yield f"http://{host}:{port}"
    server.should_exit = True
    thread.join()
