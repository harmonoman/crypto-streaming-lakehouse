"""
consumer/consumer.py

RabbitMQ consumer for trade messages.
Processes messages, writes to Postgres, and ACKs only after successful persistence.

Design contract:
    - ACK is sent AFTER the DB insert succeeds.
    - NACK (requeue=False) is sent on any failure → message routes to DLQ.
    - auto_ack=False is mandatory — never mark work done before it is done.

Usage:
    from consumer.consumer import TradeConsumer
    from consumer.repository import TradeRepository

    consumer = TradeConsumer(
        amqp_url=os.environ["AMQP_URL"],
        queue=os.environ["RABBITMQ_QUEUE"],
        repository=TradeRepository(...),
    )
    consumer.start()
"""

import json
import os
import time

import pika

from consumer.metrics import processing_duration
from shared.logger import get_logger

logger = get_logger("consumer")


class TradeConsumer:
    """
    Subscribes to crypto.trades.queue and persists each message to Postgres.

    Prefetch (QoS) limits how many unacknowledged messages are in-flight at once,
    preventing the consumer from being overwhelmed during high-throughput periods.
    """

    def __init__(
        self,
        amqp_url: str,
        queue: str,
        repository,
    ):
        self.queue = queue
        self.repository = repository

        self.connection = pika.BlockingConnection(pika.URLParameters(amqp_url))
        self.channel = self.connection.channel()

        prefetch = int(os.environ.get("CONSUMER_PREFETCH", 100))
        self.channel.basic_qos(prefetch_count=prefetch)

        logger.info("TradeConsumer connected", extra={"queue": self.queue, "prefetch": prefetch})

    def on_message(
        self,
        channel: pika.adapters.blocking_connection.BlockingChannel,
        method: pika.spec.Basic.Deliver,
        properties: pika.spec.BasicProperties,
        body: bytes,
    ) -> None:
        """
        Process a single message from the queue.

        Flow:
            1. Deserialize JSON body
            2. Insert into Postgres via repository
            3. ACK on success
            4. NACK (requeue=False) on any failure → routes to DLQ
        """
        start = time.monotonic()
        trade_id = None

        try:
            message = json.loads(body)
            trade_id = message.get("trade_id")

            self.repository.insert(message)

            # Only ACK after the DB insert succeeds.
            # If the process crashes between insert and ACK, RabbitMQ re-delivers
            # the message — the idempotent ON CONFLICT DO NOTHING insert handles it.
            duration_s = time.monotonic() - start
            processing_duration.observe(duration_s)
            channel.basic_ack(delivery_tag=method.delivery_tag)

            latency_ms = duration_s * 1000
            logger.info(
                "message_processed",
                extra={
                    "status": "success",
                    "trade_id": trade_id,
                    "queue_latency_ms": round(latency_ms, 2),
                },
            )

        except Exception as exc:
            # NACK with requeue=False — do NOT requeue.
            # requeue=True would cause an infinite retry loop for persistent failures.
            # The DLQ (configured on the queue) receives this message instead.
            duration_s = time.monotonic() - start
            processing_duration.observe(duration_s)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            latency_ms = duration_s * 1000
            logger.error(
                "message_processed",
                extra={
                    "status": "failure",
                    "trade_id": trade_id,
                    "queue_latency_ms": round(latency_ms, 2),
                    "error": str(exc),
                },
            )

    def start(self) -> None:
        """
        Begin consuming messages. Blocks until interrupted.
        Call channel.stop_consuming() from a signal handler to exit cleanly.
        """
        self.channel.basic_consume(
            queue=self.queue,
            on_message_callback=self.on_message,
            auto_ack=False,   # CRITICAL — never acknowledge before processing
        )
        logger.info("Consumer started — waiting for messages")
        self.channel.start_consuming()

    def close(self) -> None:
        """Close the connection cleanly."""
        if self.connection.is_open:
            self.connection.close()
            logger.info("TradeConsumer connection closed")
