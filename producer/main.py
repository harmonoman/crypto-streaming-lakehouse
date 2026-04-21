"""
producer/main.py

Producer entry point — connects to Coinbase WebSocket, validates
incoming trade messages, publishes to RabbitMQ, and shuts down cleanly.

Run:
    python -m producer.main

Responds to:
    SIGTERM  (docker stop / kubernetes pod eviction)
    SIGINT   (Ctrl+C)

On shutdown:
    1. Stops accepting new messages
    2. Drains the retry queue (up to 30 seconds)
    3. Closes the RabbitMQ connection
    4. Exits

Docker note:
    Set stop_grace_period: 35s in docker-compose.yml for this service
    to allow the full 30-second drain window to complete.
"""

import asyncio
import os
import signal
import time

from pydantic import ValidationError

from producer.logger import get_logger
from producer.metrics import (
    increment_invalid,
    increment_received,
    increment_valid,
    start_metrics_server,
)
from producer.publisher import RabbitMQPublisher
from producer.schemas import TradeMessage
from producer.utils import exponential_backoff
from producer.ws_client import CoinbaseWebSocketClient

logger = get_logger()

DRAIN_TIMEOUT_SECONDS = 30
MAX_RECONNECT_ATTEMPTS = 10

# ── Shutdown flag ─────────────────────────────────────────────────────────────
# Set to True when SIGTERM or SIGINT is received.
# The main loop checks this flag on each iteration.

_shutdown_requested = False


def _handle_shutdown(signum: int, frame: object) -> None:
    global _shutdown_requested
    logger.info("Shutdown signal received", extra={"signal": signum})
    _shutdown_requested = True


# ── Drain ─────────────────────────────────────────────────────────────────────

def _drain_retry_queue(publisher: RabbitMQPublisher) -> None:
    """
    Wait for the retry queue to empty before exiting.
    Gives in-flight retries up to DRAIN_TIMEOUT_SECONDS to complete.
    Logs progress every 5 seconds to avoid log noise.
    """
    if not publisher.retry_queue:
        logger.info("Retry queue empty — no drain needed")
        return

    logger.info(
        "Draining retry queue",
        extra={"remaining": len(publisher.retry_queue)},
    )
    start = time.monotonic()

    while publisher.retry_queue:
        elapsed = time.monotonic() - start

        if elapsed >= DRAIN_TIMEOUT_SECONDS:
            logger.warning(
                "Drain timeout reached — exiting with messages still in queue",
                extra={"remaining": len(publisher.retry_queue)},
            )
            break

        # Log progress every 5 seconds to avoid flooding logs
        if int(elapsed) % 5 == 0:
            logger.info(
                "Draining...",
                extra={"remaining": len(publisher.retry_queue), "elapsed_seconds": int(elapsed)},
            )

        time.sleep(0.5)

    logger.info("Drain complete")


# ── Core streaming loop ───────────────────────────────────────────────────────

async def _stream(publisher: RabbitMQPublisher) -> None:
    """
    Connect to Coinbase, subscribe, and stream trade messages.
    Validates each message and publishes clean ones to RabbitMQ.
    Reconnects with exponential backoff on connection failure.
    """
    client = CoinbaseWebSocketClient()
    attempt = 0

    while not _shutdown_requested:
        try:
            websocket = await client.connect()
            await client.subscribe(websocket)
            attempt = 0  # reset backoff on successful connection

            async for message in client.listen(websocket):
                if _shutdown_requested:
                    break

                # Only process market_trades events — skip heartbeats, subscriptions
                if message.get("channel") != "market_trades":
                    continue

                for event in message.get("events", []):
                    for trade in event.get("trades", []):
                        increment_received()

                        try:
                            validated = TradeMessage(**trade)
                            increment_valid()
                            payload = validated.model_dump_json().encode()
                            publisher.publish(payload)

                        except ValidationError as exc:
                            increment_invalid()
                            logger.error(
                                "Validation failed — message skipped",
                                extra={"error": str(exc)},
                            )

        except Exception as exc:
            if _shutdown_requested:
                break

            delay = exponential_backoff(attempt)
            logger.warning(
                "Connection lost — reconnecting",
                extra={"attempt": attempt, "backoff_seconds": delay, "error": str(exc)},
            )
            await asyncio.sleep(delay)
            attempt += 1

            if attempt >= MAX_RECONNECT_ATTEMPTS:
                logger.error(
                    "Max reconnect attempts reached — shutting down",
                    extra={"max_attempts": MAX_RECONNECT_ATTEMPTS},
                )
                break


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    start_metrics_server()

    publisher = RabbitMQPublisher(
        amqp_url=os.environ.get("AMQP_URL"),
        exchange=os.environ.get("RABBITMQ_EXCHANGE"),
        routing_key=os.environ.get("RABBITMQ_ROUTING_KEY"),
    )

    logger.info("Producer starting")

    try:
        asyncio.run(_stream(publisher))
    except (KeyboardInterrupt, SystemExit):
        # KeyboardInterrupt (SIGINT) is BaseException — not caught by asyncio.run's
        # internal handling. Catch explicitly here so finally always runs.
        logger.info("Interrupt received — beginning shutdown")
    finally:
        _drain_retry_queue(publisher)
        publisher.close()
        logger.info("Producer shutdown complete")


if __name__ == "__main__":
    main()
