"""
Logging Configuration Module - Provides a unified logger
"""

import logging
import sys
from app.core.config import get_settings


def setup_logger(name: str = "graph_rag") -> logging.Logger:
    """
    Create and configure a logger

    Args:
        name: Logger name

    Returns:
        Configured Logger instance
    """
    settings = get_settings()
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Console output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # Log format
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


# Global logger
logger = setup_logger()