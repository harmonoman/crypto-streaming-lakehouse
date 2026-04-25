"""
tests/unit/test_consumer_main.py

Unit tests for consumer/main.py — startup wiring and shutdown sequence.

All external dependencies (Postgres, RabbitMQ, BatchBuffer) are mocked
so tests run fast with no live services required.
"""

import contextlib
import signal
from unittest.mock import MagicMock, patch

import consumer.main as m
from consumer.main import _handle_shutdown, main

# ── Signal handler ────────────────────────────────────────────────────────────

def test_handle_shutdown_sets_flag():
    """_handle_shutdown must set _shutdown_requested to True."""
    m._shutdown_requested = False
    _handle_shutdown(signal.SIGTERM, None)
    assert m._shutdown_requested is True
    m._shutdown_requested = False  # reset


# ── main() wiring ─────────────────────────────────────────────────────────────

def _make_mocks():
    """Return a dict of all patched dependencies for main()."""
    return {
        "signal.signal":                "consumer.main.signal.signal",
        "psycopg2.connect":             "consumer.main.psycopg2.connect",
        "TradeRepository":              "consumer.main.TradeRepository",
        "BatchBuffer":                  "consumer.main.BatchBuffer",
        "TradeConsumer":                "consumer.main.TradeConsumer",
        "start_metrics_server":         "consumer.main.start_metrics_server",
    }


def test_main_registers_signal_handlers():
    env = {"DATABASE_URL": "postgresql://test", "AMQP_URL": "amqp://test",
           "RABBITMQ_QUEUE": "test.queue"}

    with patch.dict("os.environ", env), \
         patch("consumer.main.psycopg2.connect"), \
         patch("consumer.main.TradeRepository"), \
         patch("consumer.main.BatchBuffer"), \
         patch("consumer.main.TradeConsumer") as mock_consumer_cls, \
         patch("consumer.main.start_metrics_server"), \
         patch("consumer.main.signal.signal") as mock_signal:
        mock_consumer_cls.return_value.start.side_effect = KeyboardInterrupt
        with contextlib.suppress(Exception):
            main()

    calls = [c[0][0] for c in mock_signal.call_args_list]
    assert signal.SIGTERM in calls
    assert signal.SIGINT  in calls


def test_main_wires_buffer_as_repository():
    """consumer.repository must be replaced with the BatchBuffer instance."""
    env = {"DATABASE_URL": "postgresql://test", "AMQP_URL": "amqp://test",
           "RABBITMQ_QUEUE": "test.queue"}

    mock_buffer = MagicMock()
    mock_consumer = MagicMock()
    mock_consumer.start.side_effect = KeyboardInterrupt

    with patch.dict("os.environ", env), \
         patch("consumer.main.psycopg2.connect"), \
         patch("consumer.main.TradeRepository"), \
         patch("consumer.main.BatchBuffer", return_value=mock_buffer), \
         patch("consumer.main.TradeConsumer", return_value=mock_consumer), \
         patch("consumer.main.start_metrics_server"), \
         patch("consumer.main.signal.signal"), contextlib.suppress(Exception):
        main()

    assert mock_consumer.repository is mock_buffer


def test_main_shutdown_sequence():
    """On shutdown: flush → stop → consumer.close → db.close."""
    env = {"DATABASE_URL": "postgresql://test", "AMQP_URL": "amqp://test",
           "RABBITMQ_QUEUE": "test.queue"}

    mock_buffer   = MagicMock()
    mock_consumer = MagicMock()
    mock_consumer.start.side_effect = KeyboardInterrupt
    mock_db = MagicMock()

    with patch.dict("os.environ", env), \
         patch("consumer.main.psycopg2.connect", return_value=mock_db), \
         patch("consumer.main.TradeRepository"), \
         patch("consumer.main.BatchBuffer", return_value=mock_buffer), \
         patch("consumer.main.TradeConsumer", return_value=mock_consumer), \
         patch("consumer.main.start_metrics_server"), \
         patch("consumer.main.signal.signal"), contextlib.suppress(Exception):
        main()

    mock_buffer.flush.assert_called_once()
    mock_buffer.stop.assert_called_once()
    mock_consumer.close.assert_called_once()
    mock_db.close.assert_called_once()


def test_main_shutdown_flush_before_stop():
    """flush() must be called before stop()."""
    env = {"DATABASE_URL": "postgresql://test", "AMQP_URL": "amqp://test",
           "RABBITMQ_QUEUE": "test.queue"}

    mock_buffer   = MagicMock()
    mock_consumer = MagicMock()
    mock_consumer.start.side_effect = KeyboardInterrupt

    call_order = []
    mock_buffer.flush.side_effect = lambda: call_order.append("flush")
    mock_buffer.stop.side_effect  = lambda: call_order.append("stop")

    with patch.dict("os.environ", env), \
         patch("consumer.main.psycopg2.connect"), \
         patch("consumer.main.TradeRepository"), \
         patch("consumer.main.BatchBuffer", return_value=mock_buffer), \
         patch("consumer.main.TradeConsumer", return_value=mock_consumer), \
         patch("consumer.main.start_metrics_server"), \
         patch("consumer.main.signal.signal"), contextlib.suppress(Exception):
        main()

    assert call_order == ["flush", "stop"]
