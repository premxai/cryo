"""Structured JSON logging via structlog.

Every log line emitted anywhere in the app will be valid JSON containing:
  - timestamp (ISO 8601)
  - level
  - event (the log message)
  - request_id (if inside a request context)
  - any extra kwargs passed to the logger
"""

import logging

import structlog

from backend.config import settings


def configure_logging() -> None:
    """Configure structlog to emit newline-delimited JSON. Call once at startup."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,  # merge request_id etc.
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
