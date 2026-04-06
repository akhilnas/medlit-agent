"""Structured logging configuration using structlog.

Call ``configure_logging()`` once at application startup (in main.py) before
any logger is created.  All subsequent ``logging.getLogger(__name__)`` calls in
agents and services will automatically emit structured JSON lines.

In development (``DEBUG=true``) logs are rendered as coloured console output;
in production they are rendered as JSON.

Usage::

    from src.core.logging import configure_logging, get_logger

    configure_logging()           # call once at startup
    logger = get_logger(__name__) # anywhere in the codebase
    logger.info("article.fetched", pmid="12345678", count=10)
"""

from __future__ import annotations

import logging
import logging.config
import sys

import structlog

from src.core.config import settings


def configure_logging() -> None:
    """Configure structlog + stdlib logging for structured output."""
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.debug:
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Quiet noisy third-party loggers
    for noisy in ("httpx", "httpcore", "uvicorn.access", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger for the given module name."""
    return structlog.get_logger(name)
