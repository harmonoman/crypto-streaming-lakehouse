# shared/logger.py

import logging

from pythonjsonlogger.json import JsonFormatter


class _ServiceFilter(logging.Filter):
    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service
        return True


def get_logger(service: str) -> logging.Logger:
    logger = logging.getLogger(service)

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
    logger.addFilter(_ServiceFilter(service=service))

    return logger
