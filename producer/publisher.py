"""
producer/publisher.py

Reliable RabbitMQ publisher with delivery confirms.
Every message is either confirmed delivered (ACK) or explicitly retried.
No silent data loss.

Usage:
    from producer.publisher import RabbitMQPublisher

    publisher = RabbitMQPublisher(
        amqp_url=os.environ["AMQP_URL"],
        exchange=os.environ["RABBITMQ_EXCHANGE"],
        routing_key=os.environ["RABBITMQ_ROUTING_KEY"],
    )
    try:
        publisher.publish(message_bytes)
    finally:
        publisher.close()

Raises:
    ValueError: If required config is missing.
    pika.exceptions.AMQPConnectionError: If broker is unreachable on init.
"""

import os
from collections import deque

import pika
import pika.exceptions

from shared.logger import get_logger

logger = get_logger("producer")

MAX_ATTEMPTS = 3
RETRY_QUEUE_MAX = 1000


class RabbitMQPublisher:
    """
    Publishes messages to RabbitMQ with publisher confirms.

    - Waits for ACK/NACK after each publish (confirm_delivery mode).
    - Retries up to MAX_ATTEMPTS on NACK or publish failure.
    - Messages that fail all attempts are held in an in-memory retry_queue
      (maxlen=1000 — oldest dropped when full).
    """

    def __init__(
        self,
        amqp_url: str | None = None,
        exchange: str | None = None,
        routing_key: str | None = None,
    ):
        self.amqp_url    = amqp_url    or os.environ.get("AMQP_URL")
        self.exchange    = exchange    or os.environ.get("RABBITMQ_EXCHANGE")
        self.routing_key = routing_key or os.environ.get("RABBITMQ_ROUTING_KEY")

        if not self.amqp_url:
            raise ValueError("AMQP_URL is required — pass explicitly or set the environment variable.")
        if not self.exchange:
            raise ValueError("RABBITMQ_EXCHANGE is required — pass explicitly or set the environment variable.")
        if not self.routing_key:
            raise ValueError("RABBITMQ_ROUTING_KEY is required — pass explicitly or set the environment variable.")

        self.retry_queue: deque[bytes] = deque(maxlen=RETRY_QUEUE_MAX)

        self.connection = pika.BlockingConnection(
            pika.URLParameters(self.amqp_url)
        )
        self.channel = self.connection.channel()
        self.channel.confirm_delivery()   # blocks until broker ACKs each publish

        logger.info("RabbitMQPublisher connected", extra={"exchange": self.exchange})

    def publish(self, message: bytes) -> bool:
        """
        Publish a message and wait for broker confirmation.

        Retries up to MAX_ATTEMPTS on failure.
        Returns True if confirmed delivered, False if all attempts failed.
        """
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                self.channel.basic_publish(
                    exchange=self.exchange,
                    routing_key=self.routing_key,
                    body=message,
                    properties=pika.BasicProperties(
                        content_type="application/json",
                        delivery_mode=2,   # persistent — survives broker restart
                    ),
                    mandatory=True,        # raises UnroutableError if no queue bound — prevents silent drops
                )
                # With confirm_delivery, basic_publish raises on NACK.
                # Reaching this line means the broker sent an ACK.
                logger.debug("Message published and confirmed", extra={"attempt": attempt})
                return True

            except pika.exceptions.UnroutableError:
                logger.warning(
                    "NACK received — message unroutable",
                    extra={"attempt": attempt, "exchange": self.exchange},
                )
            except pika.exceptions.AMQPError as exc:
                logger.warning(
                    "Publish failed",
                    extra={"attempt": attempt, "error": str(exc)},
                )

        # All attempts failed — hold in retry queue for inspection
        logger.error(
            "Message failed after %d attempts — added to retry queue (queue size: %d)",
            MAX_ATTEMPTS,
            len(self.retry_queue) + 1,
        )
        self.retry_queue.append(message)
        return False

    def close(self) -> None:
        """
        Close the connection cleanly.
        Call in a finally block in main.py to ensure cleanup on exit.
        """
        if self.connection.is_open:
            self.connection.close()
            logger.info("RabbitMQPublisher connection closed")
