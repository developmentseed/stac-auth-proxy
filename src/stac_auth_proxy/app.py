"""STAC Auth Proxy API.

This module defines the FastAPI application for the STAC Auth Proxy, which handles
authentication, authorization, and proxying of requests to some internal STAC API.

"""

import os
import httpx
from fastapi import Depends, FastAPI, Request, Security
from fastapi.security import OpenIdConnect

app = FastAPI()

STAC_API_URL = os.environ.get(
    "STAC_AUTH_PROXY_UPSTREAM_API",
    "https://earth-search.aws.element84.com/v1"
)

AUTH_PROVIDER_URL = os.environ.get(
    "STAC_AUTH_PROXY_AUTH_PROVIDER",
    "https://your-openid-connect-provider.com/.well-known/openid-configuration"
)

open_id_connect_scheme = OpenIdConnect(
    openIdConnectUrl=AUTH_PROVIDER_URL
    scheme_name="OpenID Connect",
    description="OpenID Connect authentication for STAC API access",
)

@app.post("/search")
async def search_stac_api(request: Request):
    search_params = await request.json()
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{STAC_API_URL}/search", json=search_params)
    return response.json()


@app.get("/collections")
async def get_collections():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{STAC_API_URL}/collections")
    return response.json()


@app.get("/collections/{collection_id}")
async def get_collection_by_id(collection_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{STAC_API_URL}/collections/{collection_id}")
    return response.json()


@app.get("/items")
async def get_items():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{STAC_API_URL}/items")
    return response.json()


@app.get("/items/{item_id}")
async def get_item_by_id(item_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{STAC_API_URL}/items/{item_id}")
    return response.json()


@app.get("/assets/{item_id}")
async def get_assets(item_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{STAC_API_URL}/items/{item_id}/assets")
    return response.json()


@app.post("/collections/{collection_id}/items")
async def add_item_to_collection(
    collection_id: str, request: Request, token: str = Depends(open_id_connect_scheme)
):
    item = await request.json()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{STAC_API_URL}/collections/{collection_id}/items", json=item
        )
    return response.json()


@app.put("/collections/{collection_id}/items/{item_id}")
async def replace_item_in_collection(
    collection_id: str,
    item_id: str,
    request: Request,
    token: str = Depends(open_id_connect_scheme)
):
    item = await request.json()
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{STAC_API_URL}/collections/{collection_id}/items/{item_id}", json=item
        )
    return response.json()


@app.patch("/collections/{collection_id}/items/{item_id}")
async def update_item_in_collection(
    collection_id: str,
    item_id: str,
    request: Request,
    token: str = Depends(open_id_connect_scheme)
):
    item = await request.json()
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{STAC_API_URL}/collections/{collection_id}/items/{item_id}", json=item
        )
    return response.json()


@app.delete("/collections/{collection_id}/items/{item_id}")
async def delete_item_from_collection(
    collection_id: str, item_id: str, token: str = Depends(open_id_connect_scheme)
):
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{STAC_API_URL}/collections/{collection_id}/items/{item_id}"
        )
    return response.json()
