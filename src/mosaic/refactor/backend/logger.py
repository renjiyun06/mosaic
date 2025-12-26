"""Logging configuration for the backend"""
import logging
import sys
from typing import Optional


def setup_logger(
    name: str,
    level: Optional[int] = None,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """Setup a logger with consistent formatting

    Args:
        name: Logger name (typically __name__)
        level: Logging level (defaults to INFO)
        format_string: Custom format string

    Returns:
        Configured logger instance
    """
    if level is None:
        level = logging.INFO

    if format_string is None:
        format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        formatter = logging.Formatter(format_string)
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger instance with proper formatting

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance with configured formatting
    """
    logger = logging.getLogger(name)

    # Configure logger if not already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)

        # Enhanced format with timestamp, level, file location, and message
        format_string = (
            "%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s"
        )
        formatter = logging.Formatter(
            format_string,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger
