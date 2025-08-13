"""Public access to lifespan health checks.

This module re-exports the ``check_server_health`` and ``check_conformance``
utilities so that library users can import them without reaching into the
internal ``utils`` package.
"""

from .utils.lifespan import check_conformance, check_server_health

__all__ = ["check_server_health", "check_conformance"]
