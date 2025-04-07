"""
A custom integration example.

In this example, we're intentionally using a functional pattern but you could also use a
class like we do in the integrations found in stac_auth_proxy.filters.
"""

from typing import Any


def cql2_builder(admin_user: str):
    """CQL2 builder integration filter."""
    # NOTE: This is where you would set up things like connection pools.
    # NOTE: args/kwargs are passed in via environment variables.

    async def custom_integration_filter(ctx: dict[str, Any]) -> str:
        """
        Generate CQL2 expressions based on the request context.

        Returns a CQL2 expression, either as a string (cql2-text) or as a dict (cql2-json).
        """
        # NOTE: This is where you would perform a lookup from a database, API, etc.
        # NOTE: ctx is the request context, which includes the payload, headers, etc.

        if ctx["payload"] and ctx["payload"]["sub"] == admin_user:
            return "1=1"
        return "private = true"

    return custom_integration_filter
