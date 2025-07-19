"""Configuration for the STAC Auth Proxy."""

import importlib
from typing import Any, Literal, Optional, Sequence, TypeAlias, Union

from pydantic import BaseModel, Field, model_validator
from pydantic.networks import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

METHODS = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
EndpointMethods: TypeAlias = dict[str, Sequence[METHODS]]
EndpointMethodsWithScope: TypeAlias = dict[
    str, Sequence[Union[METHODS, tuple[METHODS, str]]]
]

_PREFIX_PATTERN = r"^/.*$"


class ClassInput(BaseModel):
    """Input model for dynamically loading a class or function."""

    cls: str
    args: Sequence[str] = Field(default_factory=list)
    kwargs: dict[str, str] = Field(default_factory=dict)

    def __call__(self):
        """Dynamically load a class and instantiate it with args & kwargs."""
        assert self.cls.count(":")
        module_path, class_name = self.cls.rsplit(":", 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        return cls(*self.args, **self.kwargs)


class Settings(BaseSettings):
    """Configuration settings for the STAC Auth Proxy."""

    # External URLs
    upstream_url: HttpUrl
    oidc_discovery_url: HttpUrl
    oidc_discovery_internal_url: HttpUrl

    root_path: str = ""
    override_host: bool = True
    healthz_prefix: str = Field(pattern=_PREFIX_PATTERN, default="/healthz")
    wait_for_upstream: bool = True
    check_conformance: bool = True
    enable_compression: bool = True

    # OpenAPI / Swagger UI
    openapi_spec_endpoint: Optional[str] = Field(pattern=_PREFIX_PATTERN, default=None)
    openapi_auth_scheme_name: str = "oidcAuth"
    openapi_auth_scheme_override: Optional[dict] = None
    swagger_ui_endpoint: Optional[str] = None
    swagger_ui_init_oauth: dict = Field(default_factory=dict)

    # Auth
    enable_authentication_extension: bool = True
    default_public: bool = False
    public_endpoints: EndpointMethods = {
        r"^/$": ["GET"],
        r"^/api.html$": ["GET"],
        r"^/api$": ["GET"],
        r"^/docs/oauth2-redirect": ["GET"],
        r"^/healthz": ["GET"],
    }
    private_endpoints: EndpointMethodsWithScope = {
        # https://github.com/stac-api-extensions/collection-transaction/blob/v1.0.0-beta.1/README.md#methods
        r"^/collections$": ["POST"],
        r"^/collections/([^/]+)$": ["PUT", "PATCH", "DELETE"],
        # https://github.com/stac-api-extensions/transaction/blob/v1.0.0-rc.3/README.md#methods
        r"^/collections/([^/]+)/items$": ["POST"],
        r"^/collections/([^/]+)/items/([^/]+)$": ["PUT", "PATCH", "DELETE"],
        # https://stac-utils.github.io/stac-fastapi/api/stac_fastapi/extensions/third_party/bulk_transactions/#bulktransactionextension
        r"^/collections/([^/]+)/bulk_items$": ["POST"],
    }

    # Filters
    items_filter: Optional[ClassInput] = None
    items_filter_path: str = r"^(/collections/([^/]+)/items(/[^/]+)?$|/search$)"
    collections_filter: Optional[ClassInput] = None
    collections_filter_path: str = r"^/collections(/[^/]+)?$"

    model_config = SettingsConfigDict(
        env_nested_delimiter="_",
    )

    @model_validator(mode="before")
    @classmethod
    def default_oidc_discovery_internal_url(cls, data: Any) -> Any:
        """Set the internal OIDC discovery URL to the public URL if not set."""
        if not data.get("oidc_discovery_internal_url"):
            data["oidc_discovery_internal_url"] = data.get("oidc_discovery_url")
        return data
