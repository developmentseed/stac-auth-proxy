"""Custom middleware."""

from .AddProcessTimeHeaderMiddleware import AddProcessTimeHeaderMiddleware
from .ApplyCql2FilterMiddleware import ApplyCql2FilterMiddleware
from .BuildCql2FilterMiddleware import BuildCql2FilterMiddleware
from .EnforceAuthMiddleware import EnforceAuthMiddleware
from .UpdateOpenApiMiddleware import OpenApiMiddleware

__all__ = [
    x.__name__
    for x in [
        OpenApiMiddleware,
        AddProcessTimeHeaderMiddleware,
        EnforceAuthMiddleware,
        BuildCql2FilterMiddleware,
        ApplyCql2FilterMiddleware,
    ]
]
