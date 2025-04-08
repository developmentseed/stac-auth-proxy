"""Tests for cache utilities."""

from unittest.mock import patch

import pytest

from stac_auth_proxy.utils.cache import MemoryCache, get_value_by_path


def test_memory_cache_basic_operations():
    """Test basic cache operations."""
    cache = MemoryCache(ttl=5.0)  # 5 second TTL
    key = "test_key"
    value = "test_value"

    # Test setting and getting a value
    cache[key] = value
    assert cache[key] == value
    assert key in cache

    # Test getting non-existent key
    with pytest.raises(KeyError):
        _ = cache["non_existent"]

    # Test get() method
    assert cache.get(key) == value
    assert cache.get("non_existent") is None


def test_memory_cache_expiration():
    """Test cache expiration."""
    cache = MemoryCache(ttl=5.0)  # 5 second TTL
    key = "test_key"
    value = "test_value"

    # Set initial time
    with patch("stac_auth_proxy.utils.cache.time") as mock_time:
        mock_time.return_value = 1000.0
        cache[key] = value
        assert cache[key] == value

        # Advance time past TTL
        mock_time.return_value = 1006.0  # 6 seconds later

        # Test expired key
        with pytest.raises(KeyError):
            cache[key]

        # Test contains after expiration
        assert key not in cache


def test_memory_cache_pruning():
    """Test cache pruning."""
    cache = MemoryCache(ttl=5.0)  # 5 second TTL
    key1 = "key1"
    key2 = "key2"
    value = "test_value"

    with patch("stac_auth_proxy.utils.cache.time") as mock_time:
        # Set initial time
        mock_time.return_value = 1000.0
        cache[key1] = value
        cache[key2] = value

        # Advance time past TTL
        mock_time.return_value = 1006.0  # 6 seconds later

        # Force pruning by adding a new item
        cache["key3"] = value

        # Check that expired items were pruned
        assert key1 not in cache
        assert key2 not in cache
        assert "key3" in cache


def test_memory_cache_key_str():
    """Test key string representation."""
    cache = MemoryCache()

    # Test short key
    short_key = "123"
    assert cache._key_str(short_key) == short_key

    # Test long key
    long_key = "1234567890"
    assert cache._key_str(long_key) == "123456789..."


@pytest.mark.parametrize(
    "obj, path, default, expected",
    [
        # Basic path
        ({"a": {"b": 1}}, "a.b", None, 1),
        # Nested path
        ({"a": {"b": {"c": 2}}}, "a.b.c", None, 2),
        # Non-existent path
        ({"a": {"b": 1}}, "a.c", None, None),
        # Default value
        ({"a": {"b": 1}}, "a.c", "default", "default"),
        # None in path
        ({"a": None}, "a.b", None, None),
        # Empty path
        ({"a": 1}, "", None, None),
        # Complex object
        ({"a": {"b": [1, 2, 3]}}, "a.b", None, [1, 2, 3]),
    ],
)
def test_get_value_by_path(obj, path, default, expected):
    """Test getting values by path."""
    assert get_value_by_path(obj, path, default) == expected
