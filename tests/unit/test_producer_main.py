"""
tests/unit/test_producer_main.py

Unit tests for producer/main.py — signal handlers, drain logic, and shutdown sequence.

All external dependencies (WebSocket, RabbitMQ) are mocked.
Async tests use pytest-asyncio.
"""

import contextlib
import signal
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import producer.main as m
from producer.main import _drain_retry_queue, _handle_shutdown, _stream, main

# ── Signal handler ────────────────────────────────────────────────────────────

def test_handle_shutdown_sets_flag():
    m._shutdown_requested = False
    _handle_shutdown(signal.SIGTERM, None)
    assert m._shutdown_requested is True
    m._shutdown_requested = False


# ── _drain_retry_queue ────────────────────────────────────────────────────────

def test_drain_retry_queue_empty_returns_immediately():
    publisher = MagicMock()
    publisher.retry_queue = deque()
    _drain_retry_queue(publisher)  # must not block or raise


def test_drain_retry_queue_drains_messages():
    publisher = MagicMock()
    publisher.retry_queue = deque(["msg1", "msg2"])

    def clear_queue():
        publisher.retry_queue.clear()

    # Simulate queue draining after first check
    with patch("producer.main.time.sleep", side_effect=lambda _: clear_queue()):
        _drain_retry_queue(publisher)


def test_drain_retry_queue_times_out():
    """If queue never empties, drain must exit after DRAIN_TIMEOUT_SECONDS."""
    publisher = MagicMock()
    publisher.retry_queue = deque(["stuck"])

    call_count = [0]

    def fake_monotonic():
        call_count[0] += 1
        # Simulate time progressing past timeout after a few calls
        return call_count[0] * 15.0

    with patch("producer.main.time.monotonic", side_effect=fake_monotonic), \
         patch("producer.main.time.sleep"):
        _drain_retry_queue(publisher)  # must exit without infinite loop


# ── main() shutdown sequence ──────────────────────────────────────────────────

def test_main_registers_signal_handlers():
    with patch("producer.main.signal.signal") as mock_signal, \
         patch("producer.main.start_metrics_server"), \
         patch("producer.main.RabbitMQPublisher"), \
         patch("producer.main.asyncio.run", side_effect=KeyboardInterrupt), \
         patch("producer.main._drain_retry_queue"), \
         contextlib.suppress(Exception):
        main()

    calls = [c[0][0] for c in mock_signal.call_args_list]
    assert signal.SIGTERM in calls
    assert signal.SIGINT  in calls


def test_main_calls_drain_and_close_on_shutdown():
    """On shutdown: _drain_retry_queue and publisher.close must both be called."""
    mock_publisher = MagicMock()

    with patch("producer.main.signal.signal"), \
         patch("producer.main.start_metrics_server"), \
         patch("producer.main.RabbitMQPublisher", return_value=mock_publisher), \
         patch("producer.main.asyncio.run", side_effect=KeyboardInterrupt), \
         patch("producer.main._drain_retry_queue") as mock_drain, \
         contextlib.suppress(Exception):
        main()

    mock_drain.assert_called_once_with(mock_publisher)
    mock_publisher.close.assert_called_once()


# ── _stream async logic ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_skips_non_market_trades_channel():
    """Messages from non market_trades channels must be ignored."""
    m._shutdown_requested = False

    mock_publisher = MagicMock()
    mock_ws = AsyncMock()
    mock_client = MagicMock()
    mock_client.connect = AsyncMock(return_value=mock_ws)
    mock_client.subscribe = AsyncMock()

    # Yield one non-market_trades message then set shutdown
    async def fake_listen(_):
        yield {"channel": "heartbeat"}
        m._shutdown_requested = True

    mock_client.listen = fake_listen

    with patch("producer.main.CoinbaseWebSocketClient", return_value=mock_client):
        await _stream(mock_publisher)

    mock_publisher.publish.assert_not_called()
    m._shutdown_requested = False


@pytest.mark.asyncio
async def test_stream_publishes_valid_trade():
    """Valid trade messages must be published to RabbitMQ."""
    m._shutdown_requested = False

    mock_publisher = MagicMock()
    mock_ws = AsyncMock()
    mock_client = MagicMock()
    mock_client.connect = AsyncMock(return_value=mock_ws)
    mock_client.subscribe = AsyncMock()

    trade = {
        "trade_id": "abc123",
        "price": "77853.64",
        "size": "0.01",
        "side": "buy",
        "time": "2026-04-24T15:00:00Z",
    }

    async def fake_listen(_):
        yield {"channel": "market_trades", "events": [{"trades": [trade]}]}
        m._shutdown_requested = True

    mock_client.listen = fake_listen

    with patch("producer.main.CoinbaseWebSocketClient", return_value=mock_client), \
         patch("producer.main.increment_received"), \
         patch("producer.main.increment_valid"):
        await _stream(mock_publisher)

    mock_publisher.publish.assert_called_once()
    m._shutdown_requested = False


@pytest.mark.asyncio
async def test_stream_skips_invalid_trade():
    """Invalid trade messages must be skipped — publisher not called."""
    m._shutdown_requested = False

    mock_publisher = MagicMock()
    mock_ws = AsyncMock()
    mock_client = MagicMock()
    mock_client.connect = AsyncMock(return_value=mock_ws)
    mock_client.subscribe = AsyncMock()

    invalid_trade = {"trade_id": "", "price": "-1", "size": "0", "side": "HOLD", "time": "bad"}

    async def fake_listen(_):
        yield {"channel": "market_trades", "events": [{"trades": [invalid_trade]}]}
        m._shutdown_requested = True

    mock_client.listen = fake_listen

    with patch("producer.main.CoinbaseWebSocketClient", return_value=mock_client), \
         patch("producer.main.increment_received"), \
         patch("producer.main.increment_invalid"):
        await _stream(mock_publisher)

    mock_publisher.publish.assert_not_called()
    m._shutdown_requested = False
