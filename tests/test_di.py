"""Tests for the dependency injection utility."""

from typing import Annotated

import pytest
from fastapi import Depends, Request

from stac_auth_proxy.utils.di import call_with_injected_dependencies


async def get_db_connection():
    """Mock asynchronous function to get a DB connection."""
    # pretend you open a DB connection or retrieve a session
    return "some_db_connection"


def get_special_value():
    """Mock synchronous function to get a special value."""
    return 42


async def async_func_with_dependencies(
    db_conn: Annotated[str, Depends(get_db_connection)],
    special_value: Annotated[int, Depends(get_special_value)],
):
    """Mock asynchronous dependency."""
    return (db_conn, special_value)


def sync_func_with_dependencies(
    db_conn: Annotated[str, Depends(get_db_connection)],
    special_value: Annotated[int, Depends(get_special_value)],
):
    """Mock synchronous dependency."""
    return (db_conn, special_value)


@pytest.mark.parametrize(
    "func",
    [async_func_with_dependencies, sync_func_with_dependencies],
)
@pytest.mark.asyncio
async def test_di(func):
    """Test dependency injection."""
    request = Request(
        scope={
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "query_string": b"",
        }
    )

    result = await call_with_injected_dependencies(func, request=request)
    assert result == ("some_db_connection", 42)
