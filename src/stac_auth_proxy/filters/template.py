"""Generate CQL2 filter expressions via Jinja2 templating."""

from typing import Annotated, Any

from cql2 import Expr
from fastapi import Request
from jinja2 import BaseLoader, Environment

from ..utils.requests import extract_variables


def Template(template_str: str):
    """Generate CQL2 filter expressions via Jinja2 templating."""
    env = Environment(loader=BaseLoader).from_string(template_str)

    async def dependency(
        request: Request,
        auth_token: Annotated[dict[str, Any], ...],
    ) -> Expr:
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
        cql2_str = env.render(**context).strip()
        cql2_expr = Expr(cql2_str)
        cql2_expr.validate()
        return cql2_expr

    return dependency
