"""STAC Auth Proxy API.

This module defines the FastAPI application for the STAC Auth Proxy, which handles
authentication, authorization, and proxying of requests to some internal STAC API.

"""

import os
from fastapi import Depends, FastAPI
from fastapi.security import OpenIdConnect

from .proxy import Proxy


app = FastAPI()

STAC_API_URL = os.environ.get(
    "STAC_AUTH_PROXY_UPSTREAM_API", "https://earth-search.aws.element84.com/v1"
)

AUTH_PROVIDER_URL = os.environ.get(
    "STAC_AUTH_PROXY_AUTH_PROVIDER",
    "https://your-openid-connect-provider.com/.well-known/openid-configuration",
)

open_id_connect_scheme = OpenIdConnect(
    openIdConnectUrl=AUTH_PROVIDER_URL,
    scheme_name="OpenID Connect",
    description="OpenID Connect authentication for STAC API access",
)

proxy = Proxy(upstream=STAC_API_URL)

for path, methods in {
    "/collections/{collection_id}/items": ["POST"],
    "/collections/{collection_id}/items/{item_id}": ["PUT", "PATCH", "DELETE"],
}.items():
    app.add_api_route(
        path,
        proxy.passthrough,
        methods=methods,
        dependencies=[Depends(open_id_connect_scheme)],
    )
# Catchall proxy
app.add_route("/{path:path}", proxy.passthrough)
