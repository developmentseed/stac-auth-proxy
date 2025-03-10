"""Generate CQL2 filter expressions via Jinja2 templating."""

from dataclasses import dataclass, field

from cql2 import Expr
from fastapi import Request
from jinja2 import BaseLoader, Environment

from ..utils.requests import extract_variables


@dataclass
class Template:
    """Generate CQL2 filter expressions via Jinja2 templating."""

    template_str: str
    env: Environment = field(init=False)

    def __post_init__(self):
        """Initialize the Jinja2 environment."""
        self.env = Environment(loader=BaseLoader).from_string(self.template_str)

    async def __call__(self, request: Request) -> Expr:
        """Render a CQL2 filter expression with the request and auth token."""
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
            "token": request.state.user,
        }
        cql2_str = self.env.render(**context).strip()
        cql2_expr = Expr(cql2_str)
        cql2_expr.validate()
        return cql2_expr
