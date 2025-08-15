"""
STAC Auth Proxy package.

This package contains the components for the STAC authentication and proxying system.
It includes FastAPI routes for handling authentication, authorization, and interaction
with some internal STAC API.
"""

from .app import configure_app, create_app
from .config import Settings
from .lifespan import build_lifespan

__all__ = [
    "build_lifespan",
    "create_app",
    "configure_app",
    "Settings",
]
