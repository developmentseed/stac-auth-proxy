"""Pytest fixtures."""

import threading

import pytest
import uvicorn
from fastapi import FastAPI

from stac_auth_proxy import Settings, create_app


@pytest.fixture(scope="session")
def source_api():
    """Create upstream API for testing purposes."""
    app = FastAPI()

    @app.get("/")
    def read_root():
        return {"message": "Hello from source API"}

    @app.get("/items/{item_id}")
    def read_item(item_id: int):
        return {"item_id": item_id}

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


@pytest.fixture
def proxy_app(source_api_server: str) -> FastAPI:
    """Fixture for the proxy app, pointing to the source API."""
    test_app_settings = Settings(
        upstream_url=source_api_server,
        oidc_discovery_url="https://samples.auth0.com/.well-known/openid-configuration",
        default_public=False,
        _env_file=".env.test",
    )
    print(f"{test_app_settings=}")
    return create_app(test_app_settings)
