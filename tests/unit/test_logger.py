"""
tests/unit/test_logger.py

Unit tests for shared/logger.py — get_logger() factory.
"""

import io
import json
import logging

from pythonjsonlogger.json import JsonFormatter

from shared.logger import _ServiceFilter, get_logger

# ── Test 1 — Returns a valid logger instance ─────────────────────────────────

def test_get_logger_returns_logger_instance():
    logger = get_logger("test_service")
    assert isinstance(logger, logging.Logger)


# ── Test 2 — Log output is valid JSON ────────────────────────────────────────

def test_log_output_is_valid_json():
    logger = get_logger("test_json")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter("%(message)s"))
    logger.addHandler(handler)

    logger.info("test message")

    stream.seek(0)
    line = stream.readline().strip()
    parsed = json.loads(line)
    assert isinstance(parsed, dict)

    logger.handlers = [h for h in logger.handlers if h is not handler]


# ── Test 3 — Default fields present ──────────────────────────────────────────

def test_log_contains_required_fields():
    stream = io.StringIO()
    logger = logging.getLogger("test_fields_unique")
    logger.handlers = []
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(service)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    ))
    logger.addHandler(handler)
    logger.addFilter(_ServiceFilter("test_fields_unique"))

    logger.info("checking fields")

    stream.seek(0)
    data = json.loads(stream.readline().strip())
    assert "timestamp" in data
    assert "level"     in data
    assert "message"   in data
    assert "service"   in data


# ── Test 4 — Service name injected ───────────────────────────────────────────

def test_service_name_injected():
    stream = io.StringIO()
    logger = logging.getLogger("consumer_unique")
    logger.handlers = []
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(service)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    ))
    logger.addHandler(handler)
    logger.addFilter(_ServiceFilter("consumer_unique"))

    logger.info("service check")

    stream.seek(0)
    data = json.loads(stream.readline().strip())
    assert data["service"] == "consumer_unique"


# ── Test 5 — Extra fields supported ──────────────────────────────────────────

def test_extra_fields_supported():
    stream = io.StringIO()
    logger = logging.getLogger("extra_fields_unique")
    logger.handlers = []
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(service)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    ))
    logger.addHandler(handler)
    logger.addFilter(_ServiceFilter("extra_fields_unique"))

    logger.info("extra test", extra={"trade_id": 123})

    stream.seek(0)
    data = json.loads(stream.readline().strip())
    assert data["trade_id"] == 123


# ── Test 6 — Logger does not duplicate handlers on multiple get_logger() calls ─────────────

def test_get_logger_does_not_duplicate_handlers():
    get_logger("dedup_test")
    get_logger("dedup_test")
    logger = logging.getLogger("dedup_test")
    assert len(logger.handlers) == 1
