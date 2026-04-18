"""
producer/logger.py

Structured JSON logger for the producer service.
Every log entry includes timestamp, level, service, and message.

Usage:
    from producer.logger import get_logger
    logger = get_logger()
    logger.info("WebSocket connected")
    logger.error("Connection failed", exc_info=True)
    logger.info("Trade received", extra={"trade_id": "abc123"})
"""

import logging

from pythonjsonlogger.json import JsonFormatter


class _ServiceFilter(logging.Filter):
    """Injects a fixed 'service' field into every log record."""

    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service
        return True


def get_logger() -> logging.Logger:
    """
    Return a configured JSON logger for the producer service.

    Safe to call multiple times — duplicate handlers are prevented.
    """
    logger = logging.getLogger("producer")

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(service)s",
            rename_fields={
                "asctime":   "timestamp",
                "levelname": "level",
                "name":      "logger",
            },
        )
    )
    logger.addHandler(handler)
    logger.addFilter(_ServiceFilter(service="producer"))

    return logger
