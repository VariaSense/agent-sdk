"""Structured logging configuration for Agent SDK"""

import logging
import json
import sys
import os
from typing import Any, Dict, Optional
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """JSON structured logging formatter"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "context"):
            log_data.update(record.context)

        return json.dumps(log_data)


def setup_logging(
    name: str = "agent_sdk",
    level: Optional[str] = None,
    format_json: Optional[bool] = None,
) -> logging.Logger:
    """Configure logger for Agent SDK
    
    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Defaults to env var AGENT_SDK_LOG_LEVEL
        format_json: Use JSON formatting. Defaults to env var LOG_FORMAT == 'json'
    
    Returns:
        Configured logger instance
    """
    # Get from environment if not provided
    if level is None:
        level = os.getenv("AGENT_SDK_LOG_LEVEL", "INFO")
    if format_json is None:
        format_json = os.getenv("LOG_FORMAT", "text") == "json"

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))

    # Remove existing handlers to avoid duplicates
    logger.handlers = []

    # Console handler
    handler = logging.StreamHandler(sys.stdout)

    if format_json:
        handler.setFormatter(JSONFormatter())
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


def add_context_filter(logger: logging.Logger, context: Dict[str, Any]):
    """Add context to all log records from this logger
    
    Args:
        logger: Logger instance
        context: Dictionary of context data to add
    """

    class ContextFilter(logging.Filter):
        def filter(self, record):
            record.context = context
            return True

    logger.addFilter(ContextFilter())


# Global logger instance
logger = setup_logging()
