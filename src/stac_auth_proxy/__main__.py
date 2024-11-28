import uvicorn
from uvicorn.config import LOGGING_CONFIG


LOGGING_CONFIG["loggers"][__package__] = {
    "level": "DEBUG",
    "handlers": ["default"],
}

uvicorn.run(
    f"{__package__}.app:app",
    host="0.0.0.0",
    port=8000,
    log_config=LOGGING_CONFIG,
    reload=True,
)
