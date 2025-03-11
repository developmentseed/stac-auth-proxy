"""Generate CQL2 filter expressions via Jinja2 templating."""

from dataclasses import dataclass, field
from typing import Any

from cql2 import Expr
from jinja2 import BaseLoader, Environment


@dataclass
class Template:
    """Generate CQL2 filter expressions via Jinja2 templating."""

    template_str: str
    env: Environment = field(init=False)

    def __post_init__(self):
        """Initialize the Jinja2 environment."""
        self.env = Environment(loader=BaseLoader).from_string(self.template_str)

    async def __call__(self, context: dict[str, Any]) -> Expr:
        """Render a CQL2 filter expression with the request and auth token."""
        # TODO: How to handle the case where auth_token is null?
        cql2_str = self.env.render(**context).strip()
        cql2_expr = Expr(cql2_str)
        cql2_expr.validate()
        return cql2_expr
