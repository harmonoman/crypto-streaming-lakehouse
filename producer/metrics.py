"""
producer/metrics.py

Prometheus metrics for producer message health.
Tracks how many messages are received, valid, and invalid.

Usage:
    from producer.metrics import start_metrics_server
    from producer.metrics import increment_received, increment_valid, increment_invalid

    start_metrics_server()        # call once at startup in main.py
    increment_received()          # call for every message received
    increment_valid()             # call when TradeMessage validation passes
    increment_invalid()           # call when TradeMessage validation fails

Metrics available at: http://localhost:{PRODUCER_METRICS_PORT}/metrics
"""

import os

from prometheus_client import Counter, start_http_server

# ── Counters ──────────────────────────────────────────────────────────────────
# Module-level — defined once, shared across the process.
# Prometheus requires counter names to end in _total.

messages_received_total = Counter(
    "messages_received_total",
    "Total number of messages received from the Coinbase WebSocket",
)

messages_valid_total = Counter(
    "messages_valid_total",
    "Total number of messages that passed TradeMessage validation",
)

messages_invalid_total = Counter(
    "messages_invalid_total",
    "Total number of messages that failed TradeMessage validation",
)


# ── Server ────────────────────────────────────────────────────────────────────

_server_started = False


def start_metrics_server(port: int | None = None) -> None:
    """
    Start the Prometheus HTTP server.

    Port is resolved in order:
      1. Explicit port argument
      2. PRODUCER_METRICS_PORT environment variable
      3. Default: 8000

    Safe to call multiple times — only starts once.
    Runs in a background daemon thread; does not block the application.
    """
    global _server_started
    if _server_started:
        return
    port = port or int(os.environ.get("PRODUCER_METRICS_PORT", 8000))
    start_http_server(port)
    _server_started = True


# ── Increment helpers ─────────────────────────────────────────────────────────
# Thin wrappers so callers don't import Counter objects directly.

def increment_received() -> None:
    """Call for every message received from the WebSocket."""
    messages_received_total.inc()


def increment_valid() -> None:
    """Call when a message passes TradeMessage validation."""
    messages_valid_total.inc()


def increment_invalid() -> None:
    """Call when a message fails TradeMessage validation."""
    messages_invalid_total.inc()
