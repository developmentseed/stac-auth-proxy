# Run with `uv run examples/seed-db.py`
# /// script
# dependencies = [
#   "pystac",
#   "pystac-client",
#   "stacrs",
#   "pgstacrs",
# ]
# ///
# ruff: noqa

import asyncio
import logging
import os

import stacrs
from pgstacrs import Client as PgstacClient
from pystac import Collection, Extent, ItemCollection
from pystac_client import Client as PystacClient

logger = logging.getLogger(__name__)


async def get_data_set(
    dataset_path: str, bbox: list[float], collections: str, max_items: int
):
    if not os.path.exists(dataset_path):
        logger.info(f"Downloading dataset to {dataset_path}")
        client = PystacClient.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1"
        )
        item_search = client.search(
            bbox=bbox, collections=collections, max_items=max_items
        )
        items = item_search.item_collection()
        await stacrs.write(dataset_path, list(item.to_dict() for item in items))
    else:
        logger.info(f"Loading dataset from {dataset_path}")
        item_collection = await stacrs.read(dataset_path)
        items = ItemCollection.from_dict(item_collection)

    assert os.path.exists(dataset_path), f"Dataset {dataset_path} does not exist"
    return items


async def seed_db(items: ItemCollection, db_url: str):
    logger.info(f"Seeding database with {len(items)} items")
    extent = Extent.from_items(items)
    collection = Collection(
        "naip", "NAIP data in the Planetary Computer", extent=extent
    )
    items = list(
        item.to_dict(transform_hrefs=False) for item in items
    )  # https://github.com/stac-utils/pystac/issues/960

    pgstac_client = await PgstacClient.open(db_url)
    await pgstac_client.upsert_collection(collection.to_dict())
    _ = await pgstac_client.upsert_items(items)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def main():
        colorado_naip = await get_data_set(
            dataset_path="./naip.parquet",
            bbox=[-109.0591, 36.9927, -102.04212, 41.0019],
            collections="naip",
            max_items=10000,
        )
        await seed_db(
            items=colorado_naip,
            db_url="postgresql://username:password@localhost:5439/postgis",
        )

    asyncio.run(main())
