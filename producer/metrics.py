"""
producer/metrics.py

Prometheus metrics for producer message health.
Uses shared factory functions to enforce consistent naming and prefix.

Usage:
    from producer.metrics import start_metrics_server
    from producer.metrics import increment_received, increment_valid, increment_invalid

    start_metrics_server()
    increment_received()
    increment_valid()
    increment_invalid()

Metrics available at: http://localhost:{PRODUCER_METRICS_PORT}/metrics
"""

from shared.metrics import create_counter
from shared.metrics import start_metrics_server as _start_server

# ── Counters ──────────────────────────────────────────────────────────────────

messages_received_total = create_counter(
    "messages_received_total",
    "Total number of messages received from the Coinbase WebSocket",
)

messages_valid_total = create_counter(
    "messages_valid_total",
    "Total number of messages that passed TradeMessage validation",
)

messages_invalid_total = create_counter(
    "messages_invalid_total",
    "Total number of messages that failed TradeMessage validation",
)


# ── Server ────────────────────────────────────────────────────────────────────

def start_metrics_server(port: int | None = None) -> None:
    """Start the Prometheus HTTP server for the producer on port 8000."""
    _start_server(
        port=port,
        env_var="PRODUCER_METRICS_PORT",
        default=8000,
    )


# ── Increment helpers ─────────────────────────────────────────────────────────

def increment_received() -> None:
    messages_received_total.inc()


def increment_valid() -> None:
    messages_valid_total.inc()


def increment_invalid() -> None:
    messages_invalid_total.inc()
