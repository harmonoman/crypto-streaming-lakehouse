"""
consumer/main.py

Consumer entry point — subscribes to RabbitMQ, buffers messages, and
persists them to Postgres Bronze via batch insert. Shuts down cleanly.

Run:
    python -m consumer.main

Responds to:
    SIGTERM  (docker stop)
    SIGINT   (Ctrl+C)

On shutdown:
    1. Stops consuming new messages
    2. Flushes remaining buffer to Postgres
    3. Closes RabbitMQ and Postgres connections
    4. Exits

Docker note:
    Set stop_grace_period: 35s in docker-compose.yml for this service.
"""

import os
import signal

import psycopg2

from consumer.batch_buffer import BatchBuffer
from consumer.consumer import TradeConsumer
from consumer.metrics import start_metrics_server
from consumer.repository import TradeRepository
from shared.logger import get_logger

logger = get_logger("consumer")

_shutdown_requested = False


def _handle_shutdown(signum: int, frame: object) -> None:
    global _shutdown_requested
    logger.info("Shutdown signal received", extra={"signal": signum})
    _shutdown_requested = True


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    start_metrics_server()

    db_conn = psycopg2.connect(os.environ["DATABASE_URL"])
    repository = TradeRepository(db_conn)

    batch_size = int(os.environ.get("BATCH_SIZE", 200))
    timeout_ms = int(os.environ.get("BATCH_TIMEOUT_MS", 2000))
    buffer = BatchBuffer(repository=repository, batch_size=batch_size, timeout_ms=timeout_ms)

    consumer = TradeConsumer(
        amqp_url=os.environ["AMQP_URL"],
        queue=os.environ["RABBITMQ_QUEUE"],
        repository=repository,
    )

    # Replace the direct repository insert with the batch buffer.
    # on_message now adds to the buffer instead of inserting one-by-one.
    consumer.repository = buffer

    logger.info("Consumer starting")

    try:
        consumer.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Interrupt received — beginning shutdown")
    finally:
        buffer.flush()
        buffer.stop()
        consumer.close()
        db_conn.close()
        logger.info("Consumer shutdown complete")


if __name__ == "__main__":
    main()
