"""
Unified logging for the backend.

Everything — application code (structlog), Uvicorn, and any third-party library
that uses the stdlib ``logging`` module — is rendered through a single processor
chain: pretty, colorized console output in development and line-delimited JSON in
production (set ``ENVIRONMENT=production``).

Usage:

    import structlog
    from logging_config import configure_logging

    configure_logging()  # once, at startup
    log = structlog.get_logger()
    log.info("recipe_created", recipe_id=recipe_id, name=name)

Bind per-request/per-user context once (e.g. in middleware or a dependency) with
``structlog.contextvars.bind_contextvars(...)`` and every subsequent log line in
that async context carries it automatically.
"""

import logging
import os
import sys

import structlog


def _drop_color_message(logger, method_name, event_dict):
    """
    Uvicorn attaches a redundant ANSI-colored copy of the message as a
    ``color_message`` extra; drop it so it doesn't clutter our output.
    """
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging() -> None:
    """
    Configure structlog and route stdlib logging through the same pipeline.

    Idempotent: safe to call more than once (existing handlers are replaced).
    """
    is_production = os.getenv("ENVIRONMENT", "development") == "production"

    timestamper = structlog.processors.TimeStamper(fmt="iso")

    # Runs on log records that did NOT originate from structlog (Uvicorn, libs)
    # so they get the same fields as our own events.
    foreign_pre_chain = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        _drop_color_message,
        timestamper,
    ]

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # Hand the event dict off to the stdlib ProcessorFormatter below.
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer = (
        structlog.processors.JSONRenderer()
        if is_production
        else structlog.dev.ConsoleRenderer()
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=foreign_pre_chain,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Let Uvicorn's loggers flow through the root handler instead of their own,
    # so access/error logs share the unified format.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
