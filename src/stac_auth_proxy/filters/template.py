from typing import Any, Callable

from cql2 import Expr
from jinja2 import Environment, BaseLoader
from fastapi import Request, Security

from ..utils import extract_variables

from dataclasses import dataclass, field


@dataclass
class Template:
    template_str: str
    token_dependency: Callable[..., Any]

    # Generated attributes
    env: Environment = field(init=False)

    def __post_init__(self):
        self.env = Environment(loader=BaseLoader).from_string(self.template_str)
        self.render.__annotations__["auth_token"] = Security(self.token_dependency)

    async def cql2(self, request: Request, auth_token=Security(...)) -> Expr:
        # TODO: How to handle the case where auth_token is null?
        context = {
            "req": {
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
            },
            "token": auth_token,
        }
        cql2_str = self.env.render(**context)
        cql2_expr = Expr(cql2_str)
        cql2_expr.validate()
        return cql2_expr
