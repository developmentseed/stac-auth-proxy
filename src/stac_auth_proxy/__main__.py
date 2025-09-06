"""Entry point for running the module without customized code."""

import uvicorn
from uvicorn.config import LOGGING_CONFIG

uvicorn.run(
    f"{__package__}.app:create_app",
    host="0.0.0.0",
    port=8000,
    log_config={
        **LOGGING_CONFIG,
        "loggers": {
            **LOGGING_CONFIG["loggers"],
            __package__: {
                "level": "DEBUG",
                "handlers": ["default"],
            },
        },
    },
    reload=True,
    factory=True,
)
