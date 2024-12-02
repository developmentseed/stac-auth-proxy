"""Utilities for testing."""

from typing import Callable

from stac_auth_proxy import Settings, create_app


class AppFactory:
    """Factory for creating test apps with default settings."""

    def __init__(self, **defaults):
        """Initialize the factory with default settings."""
        self.defaults = defaults

    def __call__(self, *, upstream_url, **overrides) -> Callable:
        """Create a new app with the given overrides."""
        return create_app(
            Settings.model_validate(
                {
                    **self.defaults,
                    **overrides,
                    "upstream_url": upstream_url,
                },
            )
        )
