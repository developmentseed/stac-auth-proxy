"""Generate CQL2 filter expressions via Jinja2 templating."""

from dataclasses import dataclass, field
from typing import Any

from jinja2 import BaseLoader, Environment


@dataclass
class Template:
    """Generate CQL2 filter expressions via Jinja2 templating."""

    template_str: str
    env: Environment = field(init=False)

    def __post_init__(self):
        """Initialize the Jinja2 environment."""
        self.env = Environment(loader=BaseLoader).from_string(self.template_str)

    async def __call__(self, context: dict[str, Any]) -> str:
        """Render a CQL2 filter expression with the request and auth token."""
        return self.env.render(**context).strip()
