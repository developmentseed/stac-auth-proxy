"""Lifespan manager for FastAPI applications."""

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncGenerator, Awaitable, Callable, List

from fastapi import FastAPI

logger = logging.getLogger(__name__)


@dataclass
class LifespanManager:
    """Manager for FastAPI lifespan events."""

    on_startup: List[Callable[[], Awaitable[None]]] = field(default_factory=list)
    on_teardown: List[Callable[[], Awaitable[None]]] = field(default_factory=list)

    @asynccontextmanager
    async def __call__(self, app: FastAPI) -> AsyncGenerator[None, None]:
        """FastAPI lifespan event handler."""
        for i, task in enumerate(self.on_startup):
            logger.debug(f"Executing startup task {i+1}/{len(self.on_startup)}")
            await task()

        logger.debug("All startup tasks completed successfully")

        yield

        # Execute teardown tasks
        for i, task in enumerate(self.on_teardown):
            try:
                logger.debug(f"Executing teardown task {i+1}/{len(self.on_teardown)}")
                await task()
            except Exception as e:
                logger.error(f"Teardown task failed: {e}")
