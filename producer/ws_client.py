"""
producer/ws_client.py

Thin WebSocket client for Coinbase Advanced Trade.
Connects, subscribes, and streams raw trade messages.

This class does NOT handle reconnection — that responsibility
belongs to the caller (producer/main.py).

Lifecycle contract:
    The caller owns the websocket returned by connect() and must
    close it via `await websocket.close()` or an async context manager.
"""

import json
import logging
import os

import websockets
import websockets.exceptions

logger = logging.getLogger(__name__)

# websockets.WebSocketClientProtocol is the correct type for websockets <13.0
# Update to websockets.ClientConnection when upgrading past 13.0
WebSocket = websockets.WebSocketClientProtocol


class CoinbaseWebSocketClient:

    def __init__(
        self,
        url: str | None = None,
        product_id: str = "BTC-USD",
    ):
        self.url = url or os.environ.get("WEBSOCKET_URL")
        if not self.url:
            raise ValueError(
                "WEBSOCKET_URL environment variable is not set. "
                "Pass url= explicitly or set the environment variable."
            )
        self.product_id = product_id

    async def connect(self) -> WebSocket:
        """
        Open a secure WebSocket connection to Coinbase.

        Raises websockets.exceptions.WebSocketException on failure.
        Caller is responsible for closing the returned websocket.
        """
        logger.info("Connecting to %s ...", self.url)
        websocket = await websockets.connect(
            self.url,
            open_timeout=10,       # fail fast if endpoint is unreachable
            ping_interval=20,      # keepalive ping every 20s
            ping_timeout=20,       # wait 20s for pong before closing
        )
        logger.info("Connected to %s", self.url)
        return websocket

    async def subscribe(self, websocket: WebSocket) -> None:
        """Send the subscription message for market trades."""
        payload = {
            "type": "subscribe",
            "channel": "market_trades",
            "product_ids": [self.product_id],
        }
        await websocket.send(json.dumps(payload))
        logger.info("Subscribed to market_trades / %s", self.product_id)

    async def listen(self, websocket: WebSocket):
        """
        Async generator — yields one parsed message dict per frame received.

        Yields ALL message types (subscriptions, heartbeats, market_trades).
        Filtering by channel is the caller's responsibility.

        Stops when the connection closes (clean or otherwise). The caller
        should catch websockets.exceptions.ConnectionClosed to distinguish
        a clean shutdown from a dropped connection.

        Invalid JSON frames are logged as errors and skipped — they do not
        crash the stream but should be treated as a signal of protocol issues.
        """
        try:
            async for raw in websocket:
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    logger.error(
                        "Non-JSON frame received — possible protocol issue. "
                        "Skipping. Raw (truncated): %s",
                        raw[:200],
                    )
                    continue

                logger.debug("Message received: type=%s channel=%s",
                             message.get("type"), message.get("channel"))
                yield message

        finally:
            logger.info("listen() stopped — connection closed or generator exited.")
