"""
tests/unit/test_ws_client.py

Unit tests for CoinbaseWebSocketClient.
All tests use mocked WebSockets — no real network connections.
"""

import json
import pytest
import websockets.exceptions

from unittest.mock import AsyncMock, MagicMock, patch
from producer.ws_client import CoinbaseWebSocketClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_client(url="wss://fake.coinbase.com", product_id="BTC-USD"):
    return CoinbaseWebSocketClient(url=url, product_id=product_id)


def make_mock_websocket(messages: list[str]) -> AsyncMock:
    """Return a mock websocket that yields the given raw message strings."""
    mock = AsyncMock()
    mock.__aiter__ = MagicMock(return_value=iter(messages))
    return mock


# ── __init__ ──────────────────────────────────────────────────────────────────

def test_init_uses_explicit_url():
    client = CoinbaseWebSocketClient(url="wss://explicit.url")
    assert client.url == "wss://explicit.url"


def test_init_reads_env_var(monkeypatch):
    monkeypatch.setenv("WEBSOCKET_URL", "wss://from.env")
    client = CoinbaseWebSocketClient()
    assert client.url == "wss://from.env"


def test_init_raises_if_no_url(monkeypatch):
    monkeypatch.delenv("WEBSOCKET_URL", raising=False)
    with pytest.raises(ValueError, match="WEBSOCKET_URL"):
        CoinbaseWebSocketClient()


# ── connect() ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect_returns_websocket():
    mock_ws = AsyncMock()
    with patch("producer.ws_client.websockets.connect", return_value=mock_ws) as mock_connect:
        client = make_client()
        result = await client.connect()
        mock_connect.assert_called_once_with(
            "wss://fake.coinbase.com",
            open_timeout=10,
            ping_interval=20,
            ping_timeout=20,
        )
        assert result is mock_ws


@pytest.mark.asyncio
async def test_connect_propagates_connection_error():
    with patch("producer.ws_client.websockets.connect",
               side_effect=websockets.exceptions.WebSocketException("refused")):
        client = make_client()
        with pytest.raises(websockets.exceptions.WebSocketException):
            await client.connect()


# ── subscribe() ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subscribe_sends_correct_payload():
    mock_ws = AsyncMock()
    client = make_client()
    await client.subscribe(mock_ws)

    mock_ws.send.assert_called_once()
    sent = json.loads(mock_ws.send.call_args[0][0])

    assert sent["type"] == "subscribe"
    assert sent["channel"] == "market_trades"
    assert sent["product_ids"] == ["BTC-USD"]


@pytest.mark.asyncio
async def test_subscribe_uses_configured_product_id():
    mock_ws = AsyncMock()
    client = CoinbaseWebSocketClient(url="wss://fake", product_id="ETH-USD")
    await client.subscribe(mock_ws)

    sent = json.loads(mock_ws.send.call_args[0][0])
    assert sent["product_ids"] == ["ETH-USD"]


# ── listen() ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_listen_yields_parsed_messages():
    messages = [
        json.dumps({"type": "subscriptions", "channel": "market_trades"}),
        json.dumps({"type": "update", "channel": "market_trades", "trade_id": "abc"}),
    ]
    mock_ws = make_mock_websocket(messages)
    client = make_client()

    received = [msg async for msg in client.listen(mock_ws)]

    assert len(received) == 2
    assert received[0]["type"] == "subscriptions"
    assert received[1]["trade_id"] == "abc"


@pytest.mark.asyncio
async def test_listen_skips_invalid_json(caplog):
    messages = [
        "not-valid-json",
        json.dumps({"type": "update", "trade_id": "valid"}),
    ]
    mock_ws = make_mock_websocket(messages)
    client = make_client()

    import logging
    with caplog.at_level(logging.ERROR, logger="producer.ws_client"):
        received = [msg async for msg in client.listen(mock_ws)]

    # Valid message still yielded
    assert len(received) == 1
    assert received[0]["trade_id"] == "valid"

    # Error was logged
    assert any("Non-JSON frame" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_listen_stops_on_empty_stream():
    mock_ws = make_mock_websocket([])
    client = make_client()

    received = [msg async for msg in client.listen(mock_ws)]
    assert received == []


@pytest.mark.asyncio
async def test_listen_yields_all_message_types():
    """listen() does not filter — all message types pass through."""
    messages = [
        json.dumps({"type": "subscriptions"}),
        json.dumps({"type": "heartbeat"}),
        json.dumps({"channel": "market_trades", "type": "update"}),
    ]
    mock_ws = make_mock_websocket(messages)
    client = make_client()

    received = [msg async for msg in client.listen(mock_ws)]
    assert len(received) == 3
