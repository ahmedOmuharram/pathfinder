"""Structured logging configuration."""

import logging
import sys

import structlog
from structlog.types import EventDict, Processor

from veupath_chatbot.platform.config import get_settings


def add_request_id(
    logger: logging.Logger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Add request ID to log entries if available.

    :param logger: Logger instance.
    :param _method_name: Method name (structlog processor convention).
    :param event_dict: Log event dictionary to modify.
    :returns: Updated event dict.
    """
    from veupath_chatbot.platform.context import request_id_ctx

    request_id = request_id_ctx.get()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def setup_logging() -> None:
    """Configure structured logging."""
    settings = get_settings()

    # Common processors
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        add_request_id,
    ]

    if settings.log_format == "json":
        # JSON formatting for production
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        # Console formatting for development
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
    )

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level)

    # Quiet noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structlog logger.

    :param name: Logger name (typically __name__).
    :returns: Configured bound logger.
    """
    from typing import cast

    logger = structlog.get_logger(name)
    # structlog.get_logger returns a BoundLogger after configuration
    return cast(structlog.BoundLogger, logger)
