"""Logging utilities for Jefrey.
Provides a simple init_logging that configures structured JSON logs using the standard library.
"""
import logging
import sys
import json
from pythonjsonlogger import jsonlogger

def init_logging(level: str = "INFO", logfile: str | None = None) -> None:
    """Configure root logger.
    Args:
        level: Logging level name (e.g., "DEBUG", "INFO").
        logfile: Optional path to a log file. If None logs only to stdout.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        json_ensure_ascii=False,
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers = []  # reset existing handlers
    root.addHandler(handler)
    if logfile:
        file_handler = logging.FileHandler(logfile, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

# Initialize immediately with defaults
init_logging()
