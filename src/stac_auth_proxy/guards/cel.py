from dataclasses import dataclass
from typing import Any
import re
from urllib.parse import urlparse

from fastapi import Request, Depends, HTTPException
import celpy


@dataclass
class Cel:
    """Custom middleware."""

    expression: str
    token_dependency: Any

    def __post_init__(self):
        env = celpy.Environment()
        ast = env.compile(self.expression)
        self.program = env.program(ast)

        async def check(
            request: Request,
            auth_token=Depends(self.token_dependency),
        ):
            request_data = {
                "path": request.url.path,
                "method": request.method,
                "query_params": dict(request.query_params),
                "path_params": extract_variables(request.url.path),
                "headers": dict(request.headers),
                # Body may need to be read (await request.json()) or (await request.body()) if needed
                "body": (
                    await request.json()
                    if request.headers.get("content-type") == "application/json"
                    else (await request.body()).decode()
                ),
            }

            print(f"{request_data['path_params']=}")

            result = self.program.evaluate(
                celpy.json_to_cel(
                    {
                        "req": request_data,
                        "token": auth_token,
                    }
                )
            )
            if not result:
                raise HTTPException(
                    status_code=403, detail="Forbidden (failed CEL check)"
                )

        self.check = check


def extract_variables(url: str) -> dict:
    path = urlparse(url).path
    # This allows either /items or /bulk_items, with an optional item_id following.
    pattern = r"^/collections/(?P<collection_id>[^/]+)(?:/(?:items|bulk_items)(?:/(?P<item_id>[^/]+))?)?/?$"
    match = re.match(pattern, path)
    return {k: v for k, v in match.groupdict().items() if v} if match else {}
