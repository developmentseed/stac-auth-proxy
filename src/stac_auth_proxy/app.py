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
    "STAC_AUTH_PROXY_UPSTREAM_API",
    "https://earth-search.aws.element84.com/v1",
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

# Transactions Extension Endpoins
for path, methods in {
    # https://github.com/stac-api-extensions/collection-transaction/blob/v1.0.0-beta.1/README.md#methods
    "/collections": ["POST"],
    "/collections/{collection_id}": ["PUT", "PATCH", "DELETE"],
    # https://github.com/stac-api-extensions/transaction/blob/v1.0.0-rc.3/README.md#methods
    "/collections/{collection_id}/items": ["POST"],
    "/collections/{collection_id}/items/{item_id}": ["PUT", "PATCH", "DELETE"],
    # https://stac-utils.github.io/stac-fastapi/api/stac_fastapi/extensions/third_party/bulk_transactions/#bulktransactionextension
    "/collections/{collection_id}/bulk_items": ["POST"],
}.items():
    app.add_api_route(
        path,
        proxy.passthrough,
        methods=methods,
        dependencies=[Depends(open_id_connect_scheme)],
    )

# Catchall proxy
app.add_route("/{path:path}", proxy.passthrough)
