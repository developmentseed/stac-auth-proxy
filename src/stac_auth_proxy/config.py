from typing import Optional
from pydantic.networks import HttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    upstream_url: HttpUrl = "https://earth-search.aws.element84.com/v1"
    oidc_discovery_url: HttpUrl
    openapi_spec_endpoint: Optional[str] = None

    class Config:
        env_prefix = "STAC_AUTH_PROXY_"
