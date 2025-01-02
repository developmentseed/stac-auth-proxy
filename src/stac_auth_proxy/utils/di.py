"""Dependency injection utilities for FastAPI."""

import asyncio

from fastapi import Request
from fastapi.dependencies.models import Dependant
from fastapi.dependencies.utils import (
    get_parameterless_sub_dependant,
    solve_dependencies,
)
from fastapi.params import Depends


def has_any_security_requirements(dependency: Dependant) -> bool:
    """
    Recursively check if any dependency within the hierarchy has a non-empty
    security_requirements list.
    """
    return dependency.security_requirements or any(
        has_any_security_requirements(sub_dep) for sub_dep in dependency.dependencies
    )


async def call_with_injected_dependencies(func, request: Request):
    """
    Manually solves and injects dependencies for `func` using FastAPI's internal
    dependency injection machinery.
    """
    dependant = get_parameterless_sub_dependant(
        depends=Depends(dependency=func),
        path=request.url.path,
    )

    solved = await solve_dependencies(
        request=request,
        dependant=dependant,
        # response=response,
        # body=request.body,
        body=None,
        async_exit_stack=None,
        embed_body_fields=False,
    )

    if solved.errors:
        raise RuntimeError(f"Dependency resolution error: {solved.errors}")

    results = func(**solved.values)
    if asyncio.iscoroutine(results):
        return await results
    return results
