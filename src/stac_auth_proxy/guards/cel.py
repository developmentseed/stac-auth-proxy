from typing import Any, Callable

import celpy
from fastapi import Depends, HTTPException, Request

from ..utils import extract_variables


def cel(expression: str, token_dependency: Callable[..., Any]):
    """Custom middleware."""
    env = celpy.Environment()
    ast = env.compile(expression)
    program = env.program(ast)

    async def check(
        request: Request,
        auth_token=Depends(token_dependency),
    ):
        request_data = {
            "path": request.url.path,
            "method": request.method,
            "query_params": dict(request.query_params),
            "path_params": extract_variables(request.url.path),
            "headers": dict(request.headers),
            "body": (
                await request.json()
                if request.headers.get("content-type") == "application/json"
                else (await request.body()).decode()
            ),
        }

        result = program.evaluate(
            celpy.json_to_cel(
                {
                    "req": request_data,
                    "token": auth_token,
                }
            )
        )
        if not result:
            raise HTTPException(status_code=403, detail="Forbidden (failed CEL check)")

    return check
