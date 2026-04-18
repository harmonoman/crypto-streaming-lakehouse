#!/usr/bin/env python3
"""
infra/rabbitmq_setup.py

Idempotent RabbitMQ topology bootstrap.
Safe to run on every container startup — repeated runs produce no side effects.

Usage:
    python infra/rabbitmq_setup.py

Exits 0 on success, 1 on failure.
"""

import os
import sys
import time

import pika
import pika.exceptions

# ── Constants ─────────────────────────────────────────────────────────────────

EXCHANGE        = "crypto.trades.exchange"
QUEUE           = "crypto.trades.queue"
DLQ             = "crypto.trades.dlq"
ROUTING_KEY     = "trades.raw"
DLQ_ROUTING_KEY = "trades.dead"

QUEUE_ARGS = {
    "x-dead-letter-exchange":    EXCHANGE,
    "x-dead-letter-routing-key": DLQ_ROUTING_KEY,
    "x-message-ttl":             1_800_000,    # 30 minutes in milliseconds
    "x-max-length":              100_000,      # max message count before head-drop
    "x-max-length-bytes":        524_288_000,  # 500MB hard memory cap
}

# Retry settings for startup race conditions
CONNECT_RETRIES = 5
CONNECT_DELAY_S = 5


# ── Connection ────────────────────────────────────────────────────────────────

def get_connection() -> pika.BlockingConnection:
    amqp_url = os.environ.get("AMQP_URL")
    if not amqp_url:
        print("ERROR: AMQP_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    params = pika.URLParameters(amqp_url)
    params.heartbeat = 30
    params.blocked_connection_timeout = 30

    last_exc = None
    for attempt in range(1, CONNECT_RETRIES + 1):
        try:
            print(f"Connecting to RabbitMQ (attempt {attempt}/{CONNECT_RETRIES})...")
            return pika.BlockingConnection(params)
        except pika.exceptions.AMQPConnectionError as exc:
            last_exc = exc
            if attempt < CONNECT_RETRIES:
                print(f"  connection failed: {exc}. Retrying in {CONNECT_DELAY_S}s...")
                time.sleep(CONNECT_DELAY_S)

    print(f"ERROR: Could not connect after {CONNECT_RETRIES} attempts: {last_exc}", file=sys.stderr)
    sys.exit(1)


# ── Topology ──────────────────────────────────────────────────────────────────

def declare_topology(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:

    # 1. Main exchange (direct, durable)
    channel.exchange_declare(
        exchange=EXCHANGE,
        exchange_type="direct",
        durable=True,
    )
    print(f"  exchange declared : {EXCHANGE} (direct, durable)")

    # 2. Dead-letter queue — declared before main queue so the DLX target exists
    channel.queue_declare(
        queue=DLQ,
        durable=True,
    )
    print(f"  queue declared    : {DLQ} (durable)")

    # 3. Bind DLQ to exchange with dead-letter routing key
    #    NOTE: x-dead-letter-routing-key on the main queue MUST match this key.
    #    Without an explicit DLQ routing key, RabbitMQ uses the original message
    #    routing key which will NOT match this binding — messages are silently dropped.
    channel.queue_bind(
        queue=DLQ,
        exchange=EXCHANGE,
        routing_key=DLQ_ROUTING_KEY,
    )
    print(f"  binding           : {EXCHANGE} --[{DLQ_ROUTING_KEY}]--> {DLQ}")

    # 4. Main queue with TTL, max-length, max-length-bytes, and DLX arguments
    channel.queue_declare(
        queue=QUEUE,
        durable=True,
        arguments=QUEUE_ARGS,
    )
    print(f"  queue declared    : {QUEUE} (durable)")
    print(f"    x-message-ttl        = {QUEUE_ARGS['x-message-ttl']:,} ms (30 min)")
    print(f"    x-max-length         = {QUEUE_ARGS['x-max-length']:,} messages")
    print(f"    x-max-length-bytes   = {QUEUE_ARGS['x-max-length-bytes']:,} bytes (500 MB)")
    print(f"    x-dead-letter-exchange     = {QUEUE_ARGS['x-dead-letter-exchange']}")
    print(f"    x-dead-letter-routing-key  = {QUEUE_ARGS['x-dead-letter-routing-key']}")

    # 5. Bind main queue to exchange with primary routing key
    channel.queue_bind(
        queue=QUEUE,
        exchange=EXCHANGE,
        routing_key=ROUTING_KEY,
    )
    print(f"  binding           : {EXCHANGE} --[{ROUTING_KEY}]--> {QUEUE}")


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    print("RabbitMQ topology bootstrap starting...")

    connection = get_connection()
    try:
        channel = connection.channel()
        declare_topology(channel)
    except pika.exceptions.AMQPError as exc:
        # Catches both channel-level errors (e.g. 406 PRECONDITION_FAILED on
        # argument mismatch) and any other AMQP-level failures.
        print(f"ERROR: Topology declaration failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Always close — prevents connection leaks if declare_topology raises.
        if connection.is_open:
            connection.close()

    print("RabbitMQ topology bootstrap complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
