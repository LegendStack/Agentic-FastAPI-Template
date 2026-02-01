"""Logging configuration for the application."""

import logging
import os
from logging.handlers import RotatingFileHandler

import structlog
from structlog.dev import ConsoleRenderer
from structlog.processors import JSONRenderer
from structlog.types import EventDict, Processor

from ..core.config import settings


def drop_color_message_key(_, __, event_dict: EventDict) -> EventDict:
    """Uvicorn adds `color_message` which duplicates `event`.

    Remove it to avoid double logging.
    """
    event_dict.pop("color_message", None)
    return event_dict


def file_log_filter_processors(_, __, event_dict: EventDict) -> EventDict:
    """Filter out the request ID, path, method, client host, and status code from the event dict if the
    corresponding setting is False."""

    if not settings.FILE_LOG_INCLUDE_REQUEST_ID:
        event_dict.pop("request_id", None)
    if not settings.FILE_LOG_INCLUDE_PATH:
        event_dict.pop("path", None)
    if not settings.FILE_LOG_INCLUDE_METHOD:
        event_dict.pop("method", None)
    if not settings.FILE_LOG_INCLUDE_CLIENT_HOST:
        event_dict.pop("client_host", None)
    if not settings.FILE_LOG_INCLUDE_STATUS_CODE:
        event_dict.pop("status_code", None)
    return event_dict


def console_log_filter_processors(_, __, event_dict: EventDict) -> EventDict:
    """Filter out the request ID, path, method, client host, and status code from the event dict if the
    corresponding setting is False."""

    if not settings.CONSOLE_LOG_INCLUDE_REQUEST_ID:
        event_dict.pop("request_id", None)
    if not settings.CONSOLE_LOG_INCLUDE_PATH:
        event_dict.pop("path", None)
    if not settings.CONSOLE_LOG_INCLUDE_METHOD:
        event_dict.pop("method", None)
    if not settings.CONSOLE_LOG_INCLUDE_CLIENT_HOST:
        event_dict.pop("client_host", None)
    if not settings.CONSOLE_LOG_INCLUDE_STATUS_CODE:
        event_dict.pop("status_code", None)
    return event_dict


# Shared processors for all loggers
timestamper = structlog.processors.TimeStamper(fmt="iso")
SHARED_PROCESSORS: list[Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.stdlib.ExtraAdder(),
    drop_color_message_key,
    timestamper,
    structlog.processors.StackInfoRenderer(),
]


# Configure structlog globally
structlog.configure(
    processors=SHARED_PROCESSORS + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


def build_formatter(*, json_output: bool, pre_chain: list[Processor]) -> structlog.stdlib.ProcessorFormatter:
    """Build a ProcessorFormatter with the specified renderer and processors."""
    renderer = JSONRenderer() if json_output else ConsoleRenderer()

    processors = [structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer]

    if json_output:
        pre_chain = pre_chain + [structlog.processors.format_exc_info]

    return structlog.stdlib.ProcessorFormatter(foreign_pre_chain=pre_chain, processors=processors)


# Setup log directory
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


# File handler configuration
file_handler = RotatingFileHandler(
    filename=os.path.join(LOG_DIR, "app.log"),
    maxBytes=settings.FILE_LOG_MAX_BYTES,
    backupCount=settings.FILE_LOG_BACKUP_COUNT,
)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
file_handler.setFormatter(
    build_formatter(
        json_output=settings.FILE_LOG_FORMAT_JSON, pre_chain=SHARED_PROCESSORS + [file_log_filter_processors]
    )
)

# Console handler configuration
console_handler = logging.StreamHandler()
console_handler.setLevel(settings.CONSOLE_LOG_LEVEL)
console_handler.setFormatter(
    build_formatter(
        json_output=settings.CONSOLE_LOG_FORMAT_JSON, pre_chain=SHARED_PROCESSORS + [console_log_filter_processors]
    )
)


# Root logger configuration
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers.clear()  # avoid duplicate logs
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Uvicorn logger integration
for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    logger.propagate = True
    logger.setLevel(logging.INFO)
