"""
consumer/metrics.py

Prometheus metrics for consumer message processing.
Uses shared factory functions to enforce consistent naming and prefix.

Usage:
    from consumer.metrics import processing_duration, duplicates_skipped_total, start_metrics_server

    start_metrics_server()
    processing_duration.observe(duration_s)
    duplicates_skipped_total.inc()

Metrics available at: http://localhost:{CONSUMER_METRICS_PORT}/metrics
"""

from shared.metrics import create_counter, create_histogram
from shared.metrics import start_metrics_server as _start_server

# ── Histogram ─────────────────────────────────────────────────────────────────

processing_duration = create_histogram(
    "consumer_processing_duration_seconds",
    "Time spent processing a message from receipt to ACK or NACK",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# ── Counter ───────────────────────────────────────────────────────────────────

duplicates_skipped_total = create_counter(
    "duplicates_skipped_total",
    "Total number of duplicate trade inserts silently skipped by ON CONFLICT DO NOTHING",
)


# ── Server ────────────────────────────────────────────────────────────────────

def start_metrics_server() -> None:
    """Start the Prometheus HTTP server for the consumer on port 8001."""
    _start_server(
        env_var="CONSUMER_METRICS_PORT",
        default=8001,
    )
