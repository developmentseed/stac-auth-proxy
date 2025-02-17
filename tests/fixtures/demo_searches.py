SEARCHES = [
    # Basic Spatiotemporal Search
    # {
    #     "bbox": [-122.5, 37.7, -121.8, 38.1],
    #     "datetime": "2021-01-01T00:00:00Z/2021-12-31T23:59:59Z",
    #     "limit": 10,
    # },
    # # Filtering by Collection
    # {
    #     "collections": ["landsat-8-l1"],
    #     "bbox": [-122.5, 37.7, -121.8, 38.1],
    #     "datetime": "2021-01-01T00:00:00Z/2021-12-31T23:59:59Z",
    #     "limit": 10,
    # },
    # # Property-Based Filtering (Cloud Coverage) + Sorting
    # {
    #     "collections": ["sentinel-2-l2a"],
    #     "bbox": [-10.0, 35.0, 10.0, 45.0],
    #     "datetime": "2022-05-01T00:00:00Z/2022-05-31T23:59:59Z",
    #     "query": {"eo:cloud_cover": {"lte": 10}},
    #     "sortby": [{"field": "datetime", "direction": "desc"}],
    #     "limit": 20,
    # },
    # # Search by Specific Item ID
    # {"ids": ["landsat-8-l1-image-20220515_123456"]},
    # # Search by Partial ID (Example)
    # {"query": {"id": {"like": "landsat-8-l1-image-202205%"}}},
    # # Multi-Parameter Query (Polygon, Multiple Collections, Date, Cloud Cover)
    # {
    #     "collections": ["landsat-8-l1", "sentinel-2-l2a"],
    #     "datetime": "2022-06-01T00:00:00Z/2022-06-30T23:59:59Z",
    #     "geometry": {
    #         "type": "Polygon",
    #         "coordinates": [
    #             [
    #                 [-50.0, 0.0],
    #                 [-49.0, 0.0],
    #                 [-49.0, 1.0],
    #                 [-50.0, 1.0],
    #                 [-50.0, 0.0],
    #             ]
    #         ],
    #     },
    #     "query": {"eo:cloud_cover": {"lte": 15}},
    # },
    # # Searching for Items with a Specific Asset Key
    {
        "collections": ["example-collection"],
        "bbox": [-120.5, 35.7, -120.0, 36.0],
        "datetime": "2021-06-01T00:00:00Z/2021-06-30T23:59:59Z",
        # "query": {"assets": {"contains": "NDVI"}},  # TODO: Is this valid at all?
    },
    # Using the filter Extension (CQL2)
    {
        "filter-lang": "cql2-json",
        "filter": {
            "op": "and",
            "args": [
                {"op": "=", "args": [{"property": "collection"}, "landsat-8-l1"]},
                {"op": "<=", "args": [{"property": "eo:cloud_cover"}, 20]},
                {"op": "=", "args": [{"property": "platform"}, "landsat-8"]},
            ],
        },
        "limit": 5,
    },
]
