"""
consumer/metrics.py

Prometheus metrics for consumer message processing.
Tracks end-to-end processing duration from message receipt to ACK/NACK.

Usage:
    from consumer.metrics import processing_duration, start_metrics_server

    start_metrics_server()                    # call once at startup
    processing_duration.observe(duration_s)   # call per message
"""

from prometheus_client import Histogram

from shared.metrics import start_metrics_server as _start_server

# ── Histogram ─────────────────────────────────────────────────────────────────
# Measures full message lifecycle: receipt → DB insert → ACK/NACK.
# Buckets align with our <500ms p99 SLA target.
# Prometheus standard: seconds (not milliseconds).

processing_duration = Histogram(
    "consumer_processing_duration_seconds",
    "Time spent processing a message from receipt to ACK or NACK",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
)


# ── Server ────────────────────────────────────────────────────────────────────

def start_metrics_server() -> None:
    """Start the Prometheus HTTP server for the consumer on port 8001."""
    _start_server(
        env_var="CONSUMER_METRICS_PORT",
        default=8001,
    )
