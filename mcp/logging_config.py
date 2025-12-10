"""
Structured logging configuration for MCP Server.

Outputs JSON-formatted logs with standard fields for easy querying and analysis.
Supports configurable log levels and ensures no secrets leak into logs.
"""

import logging
import os
import sys
from typing import Optional
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter that adds standard fields to all log records.

    Adds:
    - timestamp (ISO 8601)
    - level (INFO, ERROR, etc.)
    - logger name
    - message
    - Extra fields passed via logger.info(..., extra={...})
    """

    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to the log record."""
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)

        # Ensure timestamp is always present
        if not log_record.get('timestamp'):
            log_record['timestamp'] = record.created

        # Ensure level is always present
        if not log_record.get('level'):
            log_record['level'] = record.levelname

        # Ensure logger name is always present
        if not log_record.get('logger'):
            log_record['logger'] = record.name


def setup_logging(log_level: Optional[str] = None) -> logging.Logger:
    """
    Configure structured JSON logging for the MCP server.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                   If None, reads from LOG_LEVEL environment variable (default: INFO)

    Returns:
        Configured root logger

    Example:
        >>> logger = setup_logging()
        >>> logger.info("Server started", extra={"port": 8080})
        # Outputs: {"timestamp": 1234567890.123, "level": "INFO", "message": "Server started", "port": 8080}
    """
    # Get log level from parameter or environment
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Validate log level
    numeric_level = getattr(logging, log_level, None)
    if not isinstance(numeric_level, int):
        print(f"Invalid log level: {log_level}. Defaulting to INFO.", file=sys.stderr)
        numeric_level = logging.INFO
        log_level = "INFO"

    # Create JSON formatter with standard fields
    formatter = CustomJsonFormatter(
        fmt='%(timestamp)s %(level)s %(logger)s %(message)s',
        rename_fields={
            'timestamp': '@timestamp',  # Common field name for log aggregation systems
            'levelname': 'level',
            'name': 'logger'
        }
    )

    # Configure handler to write to stdout (captured by container runtime)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove any existing handlers to avoid duplicate logs
    root_logger.handlers.clear()

    # Add our JSON handler
    root_logger.addHandler(handler)

    # Log the configuration
    root_logger.info(
        "Logging configured",
        extra={
            "log_level": log_level,
            "format": "json",
            "handler": "stdout"
        }
    )

    return root_logger


def get_sanitized_extra(**kwargs) -> dict:
    """
    Sanitize extra fields to ensure no secrets leak into logs.

    Removes or redacts sensitive fields like:
    - API keys
    - Passwords
    - AWS credentials
    - Tokens

    Args:
        **kwargs: Extra fields to sanitize

    Returns:
        Sanitized dictionary safe for logging

    Example:
        >>> extra = get_sanitized_extra(user="alice", api_key="secret123")
        >>> logger.info("User logged in", extra=extra)
        # api_key will be redacted
    """
    # List of sensitive field names (case-insensitive)
    SENSITIVE_FIELDS = {
        'api_key', 'apikey', 'api-key',
        'password', 'passwd', 'pwd',
        'secret', 'secret_key', 'secret-key',
        'token', 'access_token', 'refresh_token',
        'aws_access_key_id', 'aws_secret_access_key',
        'mcp_api_key',
        'authorization', 'auth',
        'x-api-key', 'x_api_key'
    }

    sanitized = {}

    for key, value in kwargs.items():
        # Check if field name is sensitive (case-insensitive)
        if key.lower() in SENSITIVE_FIELDS:
            # Redact the value
            sanitized[key] = "<REDACTED>"
        else:
            # Keep the value as-is
            sanitized[key] = value

    return sanitized


# Context variable for request ID (will be set by middleware)
_request_id: Optional[str] = None


def set_request_id(request_id: str) -> None:
    """Set the current request ID for logging context."""
    global _request_id
    _request_id = request_id


def get_request_id() -> Optional[str]:
    """Get the current request ID."""
    return _request_id


def clear_request_id() -> None:
    """Clear the current request ID."""
    global _request_id
    _request_id = None


def log_with_context(logger: logging.Logger, level: str, message: str, **extra) -> None:
    """
    Log a message with automatic request ID context.

    Args:
        logger: Logger instance
        level: Log level (info, warning, error, etc.)
        message: Log message
        **extra: Additional fields to include

    Example:
        >>> log_with_context(logger, 'info', 'Message published', channel='market:data')
    """
    # Add request ID if available
    if _request_id:
        extra['request_id'] = _request_id

    # Sanitize extra fields
    extra = get_sanitized_extra(**extra)

    # Get the log method (info, warning, error, etc.)
    log_method = getattr(logger, level.lower())

    # Log with extra fields
    log_method(message, extra=extra)
