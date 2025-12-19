"""Tests for STAC utility functions."""

import pytest

from stac_auth_proxy.utils.stac import ensure_type


@pytest.mark.parametrize(
    "initial_value,expected_type,default_factory,expected_result",
    [
        # List type validation
        (None, list, list, []),
        ("not-a-list", list, list, []),
        (42, list, list, []),
        ({"key": "value"}, list, list, []),
        (3.14, list, list, []),
        (True, list, list, []),
        (["existing", "items"], list, list, ["existing", "items"]),
        # Dict type validation
        (None, dict, dict, {}),
        ("not-a-dict", dict, dict, {}),
        (42, dict, dict, {}),
        (["list"], dict, dict, {}),
        (3.14, dict, dict, {}),
        (True, dict, dict, {}),
        ({"existing": "value"}, dict, dict, {"existing": "value"}),
    ],
)
def test_ensure_type(initial_value, expected_type, default_factory, expected_result):
    """Test ensure_type handles various invalid types and preserves valid values."""
    data = {"field": initial_value}
    result = ensure_type(data, "field", expected_type, default_factory)

    assert result == expected_result
    assert data["field"] == expected_result
    assert isinstance(data["field"], expected_type)


def test_ensure_type_missing_key():
    """Test ensure_type when key doesn't exist in the dictionary."""
    data = {}
    result = ensure_type(data, "missing_field", list, list)

    assert result == []
    assert data["missing_field"] == []
    assert isinstance(data["missing_field"], list)


def test_ensure_type_with_custom_factory():
    """Test ensure_type with a custom default factory."""
    data = {"field": None}
    default_value = ["default", "items"]
    result = ensure_type(data, "field", list, lambda: default_value.copy())

    assert result == ["default", "items"]
    assert data["field"] == ["default", "items"]


def test_ensure_type_preserves_valid_value():
    """Test that ensure_type doesn't modify valid values."""
    original_list = ["a", "b", "c"]
    data = {"field": original_list}

    result = ensure_type(data, "field", list, list)

    # Should return the same list object, not create a new one
    assert result is original_list
    assert data["field"] is original_list


def test_ensure_type_without_factory():
    """Test ensure_type uses expected_type as factory when default_factory is not provided."""
    # Test with list
    data = {"extensions": None}
    result = ensure_type(data, "extensions", list)
    assert result == []
    assert data["extensions"] == []

    # Test with dict
    data = {"schemes": "invalid"}
    result = ensure_type(data, "schemes", dict)
    assert result == {}
    assert data["schemes"] == {}


def test_ensure_type_factory_precedence():
    """Test that explicit default_factory takes precedence over expected_type."""
    data = {"field": None}
    # Use a custom factory instead of the default list()
    result = ensure_type(data, "field", list, lambda: ["custom", "default"])

    assert result == ["custom", "default"]
    assert data["field"] == ["custom", "default"]
