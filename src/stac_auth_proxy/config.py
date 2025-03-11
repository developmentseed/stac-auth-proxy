"""Configuration for the STAC Auth Proxy."""

import importlib
from typing import Optional, Sequence, TypeAlias

from pydantic import BaseModel, Field
from pydantic.networks import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

EndpointMethods: TypeAlias = dict[str, list[str]]


class ClassInput(BaseModel):
    """Input model for dynamically loading a class or function."""

    cls: str
    args: Sequence[str] = Field(default_factory=list)
    kwargs: dict[str, str] = Field(default_factory=dict)

    def __call__(self):
        """Dynamically load a class and instantiate it with args & kwargs."""
        module_path, class_name = self.cls.rsplit(".", 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        return cls(*self.args, **self.kwargs)


class Settings(BaseSettings):
    """Configuration settings for the STAC Auth Proxy."""

    debug: bool = False

    upstream_url: HttpUrl = HttpUrl(url="https://earth-search.aws.element84.com/v1")
    oidc_discovery_url: HttpUrl

    # Endpoints
    default_public: bool = False
    private_endpoints: EndpointMethods = {
        # https://github.com/stac-api-extensions/collection-transaction/blob/v1.0.0-beta.1/README.md#methods
        r"^/collections$": ["POST"],
        r"^/collections/([^/]+)$": ["PUT", "PATCH", "DELETE"],
        # https://github.com/stac-api-extensions/transaction/blob/v1.0.0-rc.3/README.md#methods
        r"^/collections/([^/]+)/items$": ["POST"],
        r"^/collections/([^/]+)/items/([^/]+)$": ["PUT", "PATCH", "DELETE"],
        # https://stac-utils.github.io/stac-fastapi/api/stac_fastapi/extensions/third_party/bulk_transactions/#bulktransactionextension
        r"^/collections/([^/]+)/bulk_items$": ["POST"],
    }
    public_endpoints: EndpointMethods = {r"^/api.html$": ["GET"], r"^/api$": ["GET"]}
    openapi_spec_endpoint: Optional[str] = None

    collections_filter: Optional[ClassInput] = None
    collections_filter_endpoints: Optional[EndpointMethods] = {
        "/collections": ["GET"],
        "/collections/{collection_id}": ["GET"],
    }
    items_filter: Optional[ClassInput] = None
    items_filter_endpoints: Optional[EndpointMethods] = {
        r"^/search$": ["POST"],
        r"^/collections/([^/]+)/items$": ["GET", "POST"],
    }

    model_config = SettingsConfigDict(env_prefix="STAC_AUTH_PROXY_")
