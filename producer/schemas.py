"""
producer/schemas.py

Pydantic validation model for incoming Coinbase trade messages.
Rejects bad data at the boundary — before anything enters the pipeline.

Usage:
    from producer.schemas import TradeMessage
    message = TradeMessage(**raw_dict)   # raises ValidationError if invalid
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TradeMessage(BaseModel):
    trade_id: str     = Field(min_length=1)   # empty string bypasses deduplication
    price:    Decimal
    size:     Decimal
    side:     Literal["buy", "sell"]
    time:     datetime

    @field_validator("price", "size", mode="before")
    @classmethod
    def reject_float(cls, value: object) -> object:
        """
        Reject Python float inputs — floats lose precision for financial values.
        Accept strings (e.g. "50000.12") and Decimal; Pydantic handles the conversion.
        """
        if isinstance(value, float):
            raise ValueError(
                "float is not allowed — pass a string or Decimal to avoid precision loss"
            )
        return value

    @field_validator("price", "size")
    @classmethod
    def must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("must be greater than 0")
        return value

    @field_validator("time")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("time must be timezone-aware (got naive datetime)")
        return value.astimezone(UTC)
