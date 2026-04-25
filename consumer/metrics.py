"""
consumer/metrics.py

Prometheus metrics for consumer message processing.
Uses shared factory functions to enforce consistent naming and prefix.

Usage:
    from consumer.metrics import processing_duration, duplicates_skipped_total, start_metrics_server

    start_metrics_server()
    processing_duration.observe(duration_s)
    duplicates_skipped_total.inc()
    rabbitmq_queue_depth.set(depth)

Metrics available at: http://localhost:{CONSUMER_METRICS_PORT}/metrics
"""

from shared.metrics import create_counter, create_gauge, create_histogram
from shared.metrics import start_metrics_server as _start_server

# ── Histogram ─────────────────────────────────────────────────────────────────

processing_duration = create_histogram(
    "consumer_processing_duration_seconds",
    "Time spent processing a message from receipt to ACK or NACK",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# ── Counters ──────────────────────────────────────────────────────────────────

duplicates_skipped_total = create_counter(
    "duplicates_skipped_total",
    "Total number of duplicate trade inserts silently skipped by ON CONFLICT DO NOTHING",
)

# ── Gauge ─────────────────────────────────────────────────────────────────────
# Tracks the current RabbitMQ queue depth as observed by the consumer.
# Set this after each batch flush using the message count from the channel.
# A rising gauge indicates the consumer is falling behind the producer.

rabbitmq_queue_depth = create_gauge(
    "rabbitmq_queue_depth",
    "Current number of messages waiting in the RabbitMQ trade queue",
)


# ── Server ────────────────────────────────────────────────────────────────────

def start_metrics_server() -> None:
    """Start the Prometheus HTTP server for the consumer on port 8001."""
    _start_server(
        env_var="CONSUMER_METRICS_PORT",
        default=8001,
    )
