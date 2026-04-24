"""
tests/unit/test_schemas.py

Unit tests for producer/schemas.py — TradeMessage Pydantic validation model.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from producer.schemas import TradeMessage

VALID = {
    "trade_id": "abc123",
    "price":    "77853.64",
    "size":     "0.01",
    "side":     "buy",
    "time":     "2026-04-23T15:00:00Z",
}


# ── side normalization ────────────────────────────────────────────────────────

def test_lowercase_side_buy():
    """Coinbase sends 'BUY' — must be normalized to 'buy'."""
    msg = TradeMessage(**{**VALID, "side": "BUY"})
    assert msg.side == "buy"


def test_lowercase_side_sell():
    """Coinbase sends 'SELL' — must be normalized to 'sell'."""
    msg = TradeMessage(**{**VALID, "side": "SELL"})
    assert msg.side == "sell"


def test_invalid_side_raises():
    """Unknown side values must raise ValidationError."""
    with pytest.raises(ValidationError):
        TradeMessage(**{**VALID, "side": "hold"})


# ── price + size validation ───────────────────────────────────────────────────

def test_float_price_raises():
    """Float price must be rejected — use string or Decimal."""
    with pytest.raises(ValidationError):
        TradeMessage(**{**VALID, "price": 77853.64})


def test_zero_price_raises():
    """Price of zero must be rejected."""
    with pytest.raises(ValidationError):
        TradeMessage(**{**VALID, "price": "0"})


def test_negative_size_raises():
    """Negative size must be rejected."""
    with pytest.raises(ValidationError):
        TradeMessage(**{**VALID, "size": "-0.01"})


# ── trade_id validation ───────────────────────────────────────────────────────

def test_empty_trade_id_raises():
    """Empty trade_id bypasses deduplication — must be rejected."""
    with pytest.raises(ValidationError):
        TradeMessage(**{**VALID, "trade_id": ""})


# ── time validation ───────────────────────────────────────────────────────────

def test_naive_datetime_raises():
    """Timezone-naive datetime must be rejected."""
    with pytest.raises(ValidationError):
        TradeMessage(**{**VALID, "time": "2026-04-23T15:00:00"})


def test_valid_message_parses_correctly():
    """A fully valid message must parse without error."""
    msg = TradeMessage(**VALID)
    assert msg.trade_id == "abc123"
    assert msg.side == "buy"
    assert msg.price == Decimal("77853.64")
