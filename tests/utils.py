"""Utilities for testing."""

from dataclasses import dataclass, field
from typing import Callable
from stac_auth_proxy import Settings, create_app


class AppFactory:
    """Factory for creating test apps with default settings."""

    def __init__(self, **defaults):
        self.defaults = defaults

    def __call__(self, *, upstream_url, **overrides) -> Callable:
        return create_app(
            Settings.model_validate(
                {
                    **self.defaults,
                    **overrides,
                    "upstream_url": upstream_url,
                },
            )
        )
