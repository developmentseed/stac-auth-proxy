"""
STAC Auth Proxy package.

This package contains the components for the STAC authentication and proxying system.
It includes FastAPI routes for handling authentication, authorization, and interaction
with some internal STAC API.
"""

from .app import create_app
from .config import Settings

__all__ = ["create_app", "Settings"]
