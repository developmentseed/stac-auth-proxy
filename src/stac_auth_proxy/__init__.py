"""
STAC Auth Proxy package.

This package contains the components for the STAC authentication and proxying system.
It includes FastAPI routes for handling authentication, authorization, and interaction
with some internal STAC API.
"""

from .app import configure_app, create_app
from .config import Settings
from .lifespan import lifespan

__all__ = [
    "create_app",
    "configure_app",
    "lifespan",
    "Settings",
]
