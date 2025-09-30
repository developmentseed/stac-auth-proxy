"""Tests for ProcessLinksMiddleware - Refactored with parametrization."""

import pytest
from starlette.requests import Request

from stac_auth_proxy.middleware.ProcessLinksMiddleware import ProcessLinksMiddleware


@pytest.mark.parametrize(
    "content_type,should_transform",
    [
        ("application/json", True),
        ("application/geo+json", True),
        ("text/html", False),
        ("text/plain", False),
        ("application/xml", False),
    ],
)
def test_should_transform_response_content_types(content_type, should_transform):
    """Test that only JSON responses are transformed."""
    middleware = ProcessLinksMiddleware(
        app=None,
        upstream_url="http://upstream.example.com/api",
        root_path="/proxy",
    )
    request_scope = {
        "type": "http",
        "path": "/test",
        "headers": [
            (b"host", b"proxy.example.com"),
            (b"content-type", content_type.encode()),
        ],
    }
    assert (
        middleware.should_transform_response(Request(request_scope), request_scope)
        == should_transform
    )


@pytest.mark.parametrize(
    "upstream_url,root_path,input_links,expected_links",
    [
        # Basic proxy links with upstream path
        (
            "http://upstream.example.com/api",
            "/proxy",
            [
                {"rel": "self", "href": "http://proxy.example.com/api/collections"},
                {"rel": "root", "href": "http://proxy.example.com/api"},
            ],
            [
                "http://proxy.example.com/proxy/collections",
                "http://proxy.example.com/proxy",
            ],
        ),
        # Proxy links without upstream path
        (
            "http://upstream.example.com",
            "/proxy",
            [
                {"rel": "self", "href": "http://proxy.example.com/collections"},
                {"rel": "root", "href": "http://proxy.example.com/"},
            ],
            [
                "http://proxy.example.com/proxy/collections",
                "http://proxy.example.com/proxy/",
            ],
        ),
        # Proxy links without root path
        (
            "http://upstream.example.com/api",
            None,
            [
                {"rel": "self", "href": "http://proxy.example.com/api/collections"},
                {"rel": "root", "href": "http://proxy.example.com/api"},
            ],
            [
                "http://proxy.example.com/collections",
                "http://proxy.example.com",
            ],
        ),
    ],
)
def test_transform_proxy_links(upstream_url, root_path, input_links, expected_links):
    """Test transforming proxy links with different configurations."""
    middleware = ProcessLinksMiddleware(
        app=None, upstream_url=upstream_url, root_path=root_path
    )
    request_scope = {
        "type": "http",
        "path": "/test",
        "headers": [
            (b"host", b"proxy.example.com"),
            (b"content-type", b"application/json"),
        ],
    }

    data = {"links": input_links}
    transformed = middleware.transform_json(data, Request(request_scope))

    for i, expected in enumerate(expected_links):
        assert transformed["links"][i]["href"] == expected


@pytest.mark.parametrize(
    "upstream_url,root_path,input_links,expected_links",
    [
        # Upstream links with upstream path
        (
            "http://upstream.example.com/api",
            "/proxy",
            [
                {"rel": "self", "href": "http://upstream.example.com/api/collections"},
                {"rel": "root", "href": "http://upstream.example.com/api"},
                {
                    "rel": "items",
                    "href": "http://upstream.example.com/api/collections/test/items",
                },
            ],
            [
                "http://proxy.example.com/proxy/collections",
                "http://proxy.example.com/proxy",
                "http://proxy.example.com/proxy/collections/test/items",
            ],
        ),
        # Upstream links without upstream path
        (
            "http://upstream.example.com",
            "/proxy",
            [
                {"rel": "self", "href": "http://upstream.example.com/collections"},
                {"rel": "root", "href": "http://upstream.example.com/"},
            ],
            [
                "http://proxy.example.com/proxy/collections",
                "http://proxy.example.com/proxy/",
            ],
        ),
        # Upstream links without root path
        (
            "http://upstream.example.com/api",
            None,
            [
                {"rel": "self", "href": "http://upstream.example.com/api/collections"},
                {"rel": "root", "href": "http://upstream.example.com/api"},
            ],
            [
                "http://proxy.example.com/collections",
                "http://proxy.example.com",
            ],
        ),
    ],
)
def test_transform_upstream_links(upstream_url, root_path, input_links, expected_links):
    """Test transforming upstream links with different configurations."""
    middleware = ProcessLinksMiddleware(
        app=None, upstream_url=upstream_url, root_path=root_path
    )
    request_scope = {
        "type": "http",
        "path": "/test",
        "headers": [
            (b"host", b"proxy.example.com"),
            (b"content-type", b"application/json"),
        ],
    }

    data = {"links": input_links}
    transformed = middleware.transform_json(data, Request(request_scope))

    for i, expected in enumerate(expected_links):
        assert transformed["links"][i]["href"] == expected


@pytest.mark.parametrize(
    "upstream_url,root_path,port,input_links,expected_links",
    [
        # Different ports
        (
            "http://upstream.example.com:8080/api",
            "/proxy",
            3000,
            [
                {
                    "rel": "self",
                    "href": "http://upstream.example.com:8080/api/collections",
                },
            ],
            [
                "http://proxy.example.com:3000/proxy/collections",
            ],
        ),
    ],
)
def test_transform_upstream_links_with_ports(
    upstream_url, root_path, port, input_links, expected_links
):
    """Test transforming upstream links with different ports."""
    middleware = ProcessLinksMiddleware(
        app=None, upstream_url=upstream_url, root_path=root_path
    )
    request_scope = {
        "type": "http",
        "path": "/test",
        "headers": [
            (b"host", f"proxy.example.com:{port}".encode()),
            (b"content-type", b"application/json"),
        ],
    }

    data = {"links": input_links}
    transformed = middleware.transform_json(data, Request(request_scope))

    for i, expected in enumerate(expected_links):
        assert transformed["links"][i]["href"] == expected


@pytest.mark.parametrize(
    "upstream_url,root_path,input_links,expected_links",
    [
        # Different ports
        (
            "http://upstream-api:8080/",
            "",
            [
                {
                    "rel": "self",
                    "href": "http://upstream-api:8080/collections",
                },
            ],
            [
                "http://proxy.example.com/collections",
            ],
        ),
    ],
)
def test_transform_upstream_links_with_port_only_upstream(
    upstream_url, root_path, input_links, expected_links
):
    """Test transforming upstream links with different ports."""
    middleware = ProcessLinksMiddleware(
        app=None, upstream_url=upstream_url, root_path=root_path
    )
    request_scope = {
        "type": "http",
        "path": "/test",
        "headers": [
            (b"host", f"proxy.example.com".encode()),
            (b"content-type", b"application/json"),
        ],
    }

    data = {"links": input_links}
    transformed = middleware.transform_json(data, Request(request_scope))

    for i, expected in enumerate(expected_links):
        assert transformed["links"][i]["href"] == expected


def test_transform_json_different_host():
    """Test that links with different hostnames are not transformed."""
    middleware = ProcessLinksMiddleware(
        app=None,
        upstream_url="http://upstream.example.com/api",
        root_path="/proxy",
    )
    request_scope = {
        "type": "http",
        "path": "/test",
        "headers": [
            (b"host", b"proxy.example.com"),
            (b"content-type", b"application/json"),
        ],
    }

    data = {
        "links": [
            {"rel": "self", "href": "http://other.example.com/api/collections"},
            {"rel": "root", "href": "http://other.example.com/api"},
        ]
    }

    transformed = middleware.transform_json(data, Request(request_scope))

    assert transformed["links"][0]["href"] == "http://other.example.com/api/collections"
    assert transformed["links"][1]["href"] == "http://other.example.com/api"


def test_transform_json_invalid_link():
    """Test that invalid links are handled gracefully."""
    middleware = ProcessLinksMiddleware(
        app=None,
        upstream_url="http://upstream.example.com/api",
        root_path="/proxy",
    )
    request_scope = {
        "type": "http",
        "path": "/test",
        "headers": [
            (b"host", b"proxy.example.com"),
            (b"content-type", b"application/json"),
        ],
    }

    data = {
        "links": [
            {"rel": "self", "href": "not-a-url"},
            {"rel": "root", "href": "http://proxy.example.com/api"},
        ]
    }

    transformed = middleware.transform_json(data, Request(request_scope))

    assert transformed["links"][0]["href"] == "not-a-url"
    assert transformed["links"][1]["href"] == "http://proxy.example.com/proxy"


def test_transform_json_nested_links():
    """Test transforming links in nested STAC objects."""
    middleware = ProcessLinksMiddleware(
        app=None,
        upstream_url="http://upstream.example.com/api",
        root_path="/proxy",
    )
    request_scope = {
        "type": "http",
        "path": "/test",
        "headers": [
            (b"host", b"proxy.example.com"),
            (b"content-type", b"application/json"),
        ],
    }

    data = {
        "links": [
            {"rel": "self", "href": "http://proxy.example.com/api/collections"},
        ],
        "collections": [
            {
                "id": "test-collection",
                "links": [
                    {
                        "rel": "items",
                        "href": "http://proxy.example.com/api/collections/test-collection/items",
                    },
                ],
            }
        ],
    }

    transformed = middleware.transform_json(data, Request(request_scope))

    # Top-level links should be transformed
    assert (
        transformed["links"][0]["href"] == "http://proxy.example.com/proxy/collections"
    )

    # Nested links should also be transformed
    assert (
        transformed["collections"][0]["links"][0]["href"]
        == "http://proxy.example.com/proxy/collections/test-collection/items"
    )


def test_transform_without_prefix():
    """Test transforming links without root_path prefix."""
    middleware = ProcessLinksMiddleware(
        app=None,
        upstream_url="http://upstream.example.com/api",
        root_path=None,
    )
    request_scope = {
        "type": "http",
        "path": "/test",
        "headers": [
            (b"host", b"proxy.example.com"),
            (b"content-type", b"application/json"),
        ],
    }

    data = {
        "links": [
            {"rel": "self", "href": "http://proxy.example.com/api/collections"},
            {"rel": "data", "href": "http://proxy.example.com/collections"},
        ]
    }
    transformed = middleware.transform_json(data, Request(request_scope))
    assert transformed["links"][0]["href"] == "http://proxy.example.com/collections"
    assert transformed["links"][1]["href"] == "http://proxy.example.com/collections"


@pytest.mark.parametrize(
    "upstream_url,root_path,input_links,expected_links",
    [
        # Upstream links with upstream path
        (
            "http://upstream.example.com/api",
            "/proxy",
            [
                {"rel": "self", "href": "http://upstream.example.com/api/collections"},
                {"rel": "root", "href": "http://upstream.example.com/api"},
                {
                    "rel": "items",
                    "href": "http://upstream.example.com/api/collections/test/items",
                },
            ],
            [
                "http://proxy.example.com/proxy/collections",
                "http://proxy.example.com/proxy",
                "http://proxy.example.com/proxy/collections/test/items",
            ],
        ),
        # Upstream links without upstream path
        (
            "http://upstream.example.com",
            "/proxy",
            [
                {"rel": "self", "href": "http://upstream.example.com/collections"},
                {"rel": "root", "href": "http://upstream.example.com/"},
                {"rel": "root", "href": "http://upstream.example.com/other/path"},
            ],
            [
                "http://proxy.example.com/proxy/collections",
                "http://proxy.example.com/proxy/",
                "http://proxy.example.com/proxy/other/path",
            ],
        ),
        # Upstream links without root path
        (
            "http://upstream.example.com/api",
            None,
            [
                {"rel": "self", "href": "http://upstream.example.com/api/collections"},
                {"rel": "root", "href": "http://upstream.example.com/api"},
                {"rel": "root", "href": "http://upstream.example.com/other/path"},
            ],
            [
                "http://proxy.example.com/collections",
                "http://proxy.example.com",
                # Upstream links without matching root path should be ignored
                "http://upstream.example.com/other/path",
            ],
        ),
    ],
)
def test_transform_mixed_links(upstream_url, root_path, input_links, expected_links):
    """Test transforming a mix of proxy links and upstream links."""
    middleware = ProcessLinksMiddleware(
        app=None,
        upstream_url=upstream_url,
        root_path=root_path,
    )
    request_scope = {
        "type": "http",
        "path": "/test",
        "headers": [
            (b"host", b"proxy.example.com"),
            (b"content-type", b"application/json"),
        ],
    }

    transformed = middleware.transform_json(
        {
            "links": input_links,
        },
        Request(request_scope),
    )

    for i, expected in enumerate(expected_links):
        assert transformed["links"][i]["href"] == expected


def test_transform_upstream_links_nested_objects():
    """Test transforming upstream links in nested STAC objects."""
    middleware = ProcessLinksMiddleware(
        app=None,
        upstream_url="http://upstream.example.com/api",
        root_path="/proxy",
    )
    request_scope = {
        "type": "http",
        "path": "/test",
        "headers": [
            (b"host", b"proxy.example.com"),
            (b"content-type", b"application/json"),
        ],
    }

    data = {
        "links": [
            {"rel": "self", "href": "http://upstream.example.com/api"},
        ],
        "collections": [
            {
                "id": "test-collection",
                "links": [
                    {
                        "rel": "items",
                        "href": "http://upstream.example.com/api/collections/test-collection/items",
                    },
                ],
            }
        ],
    }

    transformed = middleware.transform_json(data, Request(request_scope))

    # Top-level links should be transformed
    assert transformed["links"][0]["href"] == "http://proxy.example.com/proxy"

    # Nested links should also be transformed
    assert (
        transformed["collections"][0]["links"][0]["href"]
        == "http://proxy.example.com/proxy/collections/test-collection/items"
    )


@pytest.mark.parametrize(
    "headers,expected_base_url",
    [
        # X-Forwarded-* headers
        (
            [
                (b"host", b"internal-proxy:8080"),
                (b"content-type", b"application/json"),
                (b"x-forwarded-host", b"api.example.com"),
                (b"x-forwarded-proto", b"https"),
                (b"x-forwarded-path", b"/api/v1"),
            ],
            "https://api.example.com",
        ),
        # Partial X-Forwarded-* headers
        (
            [
                (b"host", b"internal-proxy:8080"),
                (b"content-type", b"application/json"),
                (b"x-forwarded-host", b"api.example.com"),
            ],
            "http://api.example.com",  # Falls back to request scheme
        ),
        # No forwarded headers
        (
            [
                (b"host", b"proxy.example.com"),
                (b"content-type", b"application/json"),
            ],
            "http://proxy.example.com",
        ),
        # Standard Forwarded header
        (
            [
                (b"host", b"internal-proxy:8080"),
                (b"content-type", b"application/json"),
                (
                    b"forwarded",
                    b"for=192.0.2.43; by=203.0.113.60; proto=https; host=api.example.com",
                ),
            ],
            "https://api.example.com",
        ),
        # Forwarded header with multiple proxies
        (
            [
                (b"host", b"internal-proxy:8080"),
                (b"content-type", b"application/json"),
                (
                    b"forwarded",
                    b"for=192.0.2.43, for=198.51.100.17; by=203.0.113.60; proto=https; host=api.example.com",
                ),
            ],
            "https://api.example.com",
        ),
        # Forwarded header with quoted values
        (
            [
                (b"host", b"internal-proxy:8080"),
                (b"content-type", b"application/json"),
                (
                    b"forwarded",
                    b'for="192.0.2.43"; by="203.0.113.60"; proto="https"; host="api.example.com"',
                ),
            ],
            "https://api.example.com",
        ),
        # Forwarded header with partial info
        (
            [
                (b"host", b"internal-proxy:8080"),
                (b"content-type", b"application/json"),
                (b"forwarded", b"for=192.0.2.43; host=api.example.com"),
            ],
            "http://api.example.com",  # Falls back to request scheme
        ),
        # Forwarded header priority over X-Forwarded-*
        (
            [
                (b"host", b"internal-proxy:8080"),
                (b"content-type", b"application/json"),
                (b"x-forwarded-host", b"x-forwarded.example.com"),
                (b"x-forwarded-proto", b"http"),
                (b"forwarded", b"for=192.0.2.43; proto=https; host=api.example.com"),
            ],
            "https://api.example.com",
        ),
        # Malformed Forwarded header falls back to X-Forwarded-*
        (
            [
                (b"host", b"internal-proxy:8080"),
                (b"content-type", b"application/json"),
                (b"x-forwarded-host", b"api.example.com"),
                (b"x-forwarded-proto", b"https"),
                (b"forwarded", b"malformed header content"),
            ],
            "https://api.example.com",
        ),
    ],
)
def test_transform_with_forwarded_headers(headers, expected_base_url):
    """Test transforming links with various forwarded header scenarios."""
    middleware = ProcessLinksMiddleware(
        app=None, upstream_url="http://upstream.example.com/api", root_path="/proxy"
    )
    request_scope = {
        "type": "http",
        "path": "/test",
        "headers": headers,
    }

    data = {
        "links": [
            {"rel": "self", "href": "http://upstream.example.com/api/collections"},
            {"rel": "root", "href": "http://upstream.example.com/api"},
        ]
    }

    transformed = middleware.transform_json(data, Request(request_scope))

    # Should use the forwarded headers to construct the correct client URL
    # but not include the forwarded path in the response URLs
    assert transformed["links"][0]["href"] == f"{expected_base_url}/proxy/collections"
    assert transformed["links"][1]["href"] == f"{expected_base_url}/proxy"


@pytest.mark.parametrize(
    "upstream_url,request_host,request_port,scheme,input_links,expected_links",
    [
        # Test case 1: Non-standard port (should work correctly)
        (
            "http://montandon-eoapi-stac:8080",
            "stac-test.whydidweevendothis.com",
            1234,
            "http",
            [
                {"rel": "self", "href": "http://montandon-eoapi-stac:8080/collections"},
            ],
            [
                "http://stac-test.whydidweevendothis.com:1234/collections",
            ],
        ),
        # Test case 2: Standard port HTTP (80) - BUG: should NOT include upstream port
        (
            "http://montandon-eoapi-stac:8080",
            "stac-test.whydidweevendothis.com",
            80,
            "http",
            [
                {"rel": "self", "href": "http://montandon-eoapi-stac:8080/collections"},
            ],
            [
                "http://stac-test.whydidweevendothis.com/collections",  # Should NOT have :8080
            ],
        ),
        # Test case 3: Standard port HTTPS (443) - BUG: should NOT include upstream port
        (
            "http://montandon-eoapi-stac:8080",
            "stac-test.whydidweevendothis.com",
            443,
            "https",
            [
                {"rel": "self", "href": "http://montandon-eoapi-stac:8080/collections"},
            ],
            [
                "https://stac-test.whydidweevendothis.com/collections",  # Should NOT have :8080
            ],
        ),
        # Test case 4: Standard port but NO server info (simulate real-world missing port)
        (
            "http://montandon-eoapi-stac:8080",
            "stac-test.whydidweevendothis.com",
            None,  # No port specified - simulate real-world scenario
            "https",
            [
                {"rel": "self", "href": "http://montandon-eoapi-stac:8080/collections"},
            ],
            [
                "https://stac-test.whydidweevendothis.com/collections",  # Should NOT have :8080
            ],
        ),
    ],
)
def test_transform_upstream_links_standard_ports_bug(
    upstream_url, request_host, request_port, scheme, input_links, expected_links
):
    """Test that demonstrates the port handling bug with standard ports.
    
    This test demonstrates the issue where standard ports (80, 443) cause
    the upstream port to appear in the final URLs incorrectly.
    """
    middleware = ProcessLinksMiddleware(
        app=None, upstream_url=upstream_url, root_path=None
    )
    
    # Simulate request coming through standard port (80 or 443)
    # For standard ports, browsers don't include port in Host header and ASGI scope
    if request_port is None:
        # Simulate real-world scenario where port is not specified anywhere
        host_header = request_host  # No port in Host header
        server_info = (request_host, 443)  # Server might default to 443 for HTTPS
    elif request_port in [80, 443]:
        host_header = request_host  # No port in Host header for standard ports
        server_info = (request_host, request_port)  # But server info might be available
    else:
        host_header = f"{request_host}:{request_port}"  # Non-standard ports include port
        server_info = (request_host, request_port)
    
    request_scope = {
        "type": "http",
        "scheme": scheme,
        "path": "/test",
        "headers": [
            (b"host", host_header.encode()),
            (b"content-type", b"application/json"),
        ],
        "server": server_info,
    }

    data = {"links": input_links}
    transformed = middleware.transform_json(data, Request(request_scope))

    for i, expected in enumerate(expected_links):
        actual = transformed["links"][i]["href"]
        print(f"Test case: port {request_port}")
        print(f"Expected: {expected}")
        print(f"Actual:   {actual}")
        assert actual == expected, f"Port {request_port} test failed: expected {expected}, got {actual}"


def test_transform_upstream_links_no_host_port_edge_case():
    """Test the specific edge case that causes the bug.
    
    This test simulates what happens when:
    1. Browser accesses http://localhost (no port in Host header)
    2. Server is running on port 8000 internally
    3. Upstream URL has port 8080
    4. The bug: final URLs incorrectly show :8080 instead of no port
    """
    middleware = ProcessLinksMiddleware(
        app=None, 
        upstream_url="http://montandon-eoapi-stac:8080", 
        root_path=None
    )
    
    # Simulate the exact scenario that fails:
    # - Host header: just "localhost" (no port)
    # - Server port: 8000 (internal container port)
    # - Scheme: http
    # - Expected result: http://localhost/collections (no port)
    # - Bug: gets http://localhost:8080/collections (upstream port!)
    request_scope = {
        "type": "http",
        "scheme": "http",
        "path": "/collections",
        "query_string": b"",
        "headers": [
            (b"host", b"localhost"),  # NO PORT in host header
            (b"content-type", b"application/json"),
        ],
        "server": ("127.0.0.1", 8000),  # Internal server port
    }

    # Test with a link from upstream that has port 8080
    data = {
        "links": [
            {"rel": "self", "href": "http://montandon-eoapi-stac:8080/collections"},
        ]
    }
    
    # This should transform to http://localhost/collections (no port)
    transformed = middleware.transform_json(data, Request(request_scope))
    actual = transformed["links"][0]["href"]
    expected = "http://localhost/collections"
    
    print(f"Edge case test:")
    print(f"Expected: {expected}")
    print(f"Actual:   {actual}")
    
    # This test should FAIL and demonstrate the bug
    assert actual == expected, f"Edge case failed: expected {expected}, got {actual}"
