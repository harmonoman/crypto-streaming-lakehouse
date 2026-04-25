"""
tests/unit/test_consumer.py

Unit tests for consumer/consumer.py — TradeConsumer message handling.

All RabbitMQ dependencies are mocked — no live broker required.
"""

import json
from unittest.mock import MagicMock, patch

from consumer.consumer import TradeConsumer


def _make_consumer():
    """Build a TradeConsumer with fully mocked RabbitMQ connection."""
    with patch("consumer.consumer.pika.BlockingConnection") as mock_conn_cls:
        mock_conn = MagicMock()
        mock_channel = MagicMock()
        mock_conn.channel.return_value = mock_channel
        mock_conn_cls.return_value = mock_conn

        repo = MagicMock()
        consumer = TradeConsumer(
            amqp_url="amqp://test_user:test_pass@localhost:5672/",
            queue="test.queue",
            repository=repo,
        )
        consumer.channel = mock_channel
        return consumer, mock_channel, repo


def _make_delivery(delivery_tag=1):
    method = MagicMock()
    method.delivery_tag = delivery_tag
    properties = MagicMock()
    return method, properties


def _make_body(trade_id="abc123", price="77853.64", size="0.01", side="buy"):
    return json.dumps({
        "trade_id": trade_id,
        "price":    price,
        "size":     size,
        "side":     side,
        "time":     "2026-04-24T15:00:00Z",
    }).encode()


# ── on_message — success path ─────────────────────────────────────────────────

def test_on_message_calls_insert_one():
    """Successful message must call repository.insert_one."""
    consumer, channel, repo = _make_consumer()
    method, props = _make_delivery()
    body = _make_body()

    with patch("consumer.consumer.processing_duration"):
        consumer.on_message(channel, method, props, body)

    repo.insert_one.assert_called_once()
    call_arg = repo.insert_one.call_args[0][0]
    assert call_arg["trade_id"] == "abc123"


def test_on_message_acks_on_success():
    """Successful processing must ACK the message."""
    consumer, channel, repo = _make_consumer()
    method, props = _make_delivery(delivery_tag=42)
    body = _make_body()

    with patch("consumer.consumer.processing_duration"):
        consumer.on_message(channel, method, props, body)

    channel.basic_ack.assert_called_once_with(delivery_tag=42)
    channel.basic_nack.assert_not_called()


def test_on_message_records_processing_duration_on_success():
    """Processing duration metric must be observed on success."""
    consumer, channel, repo = _make_consumer()
    method, props = _make_delivery()
    body = _make_body()

    with patch("consumer.consumer.processing_duration") as mock_duration:
        consumer.on_message(channel, method, props, body)

    mock_duration.observe.assert_called_once()
    observed_value = mock_duration.observe.call_args[0][0]
    assert observed_value >= 0


# ── on_message — failure path ─────────────────────────────────────────────────

def test_on_message_nacks_on_repository_failure():
    """If repository raises, message must be NACKed with requeue=False."""
    consumer, channel, repo = _make_consumer()
    repo.insert_one.side_effect = Exception("DB connection lost")
    method, props = _make_delivery(delivery_tag=99)
    body = _make_body()

    with patch("consumer.consumer.processing_duration"):
        consumer.on_message(channel, method, props, body)

    channel.basic_nack.assert_called_once_with(delivery_tag=99, requeue=False)
    channel.basic_ack.assert_not_called()


def test_on_message_nacks_on_invalid_json():
    """Invalid JSON body must be NACKed — not crash the consumer."""
    consumer, channel, repo = _make_consumer()
    method, props = _make_delivery()
    body = b"not valid json {"

    with patch("consumer.consumer.processing_duration"):
        consumer.on_message(channel, method, props, body)

    channel.basic_nack.assert_called_once()
    nack_kwargs = channel.basic_nack.call_args[1]
    assert nack_kwargs["requeue"] is False


def test_on_message_records_processing_duration_on_failure():
    """Processing duration metric must be observed even on failure."""
    consumer, channel, repo = _make_consumer()
    repo.insert_one.side_effect = Exception("timeout")
    method, props = _make_delivery()
    body = _make_body()

    with patch("consumer.consumer.processing_duration") as mock_duration:
        consumer.on_message(channel, method, props, body)

    mock_duration.observe.assert_called_once()


# ── close() ───────────────────────────────────────────────────────────────────

def test_close_closes_open_connection():
    """close() must close the connection if it is open."""
    consumer, channel, repo = _make_consumer()
    consumer.connection.is_open = True

    consumer.close()

    consumer.connection.close.assert_called_once()


def test_close_skips_already_closed_connection():
    """close() must not crash if connection is already closed."""
    consumer, channel, repo = _make_consumer()
    consumer.connection.is_open = False

    consumer.close()  # must not raise
    consumer.connection.close.assert_not_called()
