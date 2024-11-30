from typing import Optional, TypeAlias

from pydantic import Json
from pydantic.networks import HttpUrl
from pydantic_settings import BaseSettings

EndpointMethods: TypeAlias = dict[str, list[str]]


class Settings(BaseSettings):
    upstream_url: HttpUrl = "https://earth-search.aws.element84.com/v1"
    oidc_discovery_url: HttpUrl

    # Endpoints
    default_public: bool = False
    private_endpoints: EndpointMethods = {
        # https://github.com/stac-api-extensions/collection-transaction/blob/v1.0.0-beta.1/README.md#methods
        "/collections": ["POST"],
        "/collections/{collection_id}": ["PUT", "PATCH", "DELETE"],
        # https://github.com/stac-api-extensions/transaction/blob/v1.0.0-rc.3/README.md#methods
        "/collections/{collection_id}/items": ["POST"],
        "/collections/{collection_id}/items/{item_id}": ["PUT", "PATCH", "DELETE"],
        # https://stac-utils.github.io/stac-fastapi/api/stac_fastapi/extensions/third_party/bulk_transactions/#bulktransactionextension
        "/collections/{collection_id}/bulk_items": ["POST"],
    }
    public_endpoints: EndpointMethods = {"/api.html": ["GET"]}
    openapi_spec_endpoint: Optional[str] = None

    class Config:
        env_prefix = "STAC_AUTH_PROXY_"
