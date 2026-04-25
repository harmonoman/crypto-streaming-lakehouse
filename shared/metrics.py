"""
shared/metrics.py

Shared Prometheus utilities for all pipeline services.

Two responsibilities:
  1. start_metrics_server() — start the HTTP scrape endpoint once per service
  2. create_counter() / create_histogram() — metric factories with consistent naming

Why prefix all metrics with "crypto_pipeline_"?
    Prometheus scrapes metrics from many services. A consistent prefix ensures
    all pipeline metrics are grouped together and easy to filter in dashboards.

Why a local cache for duplicate safety?
    Prometheus raises ValueError if a metric name is registered twice.
    A simple dict cache returns the existing metric on subsequent calls —
    no private Prometheus internals, no try/except complexity.

Usage:
    from shared.metrics import start_metrics_server, create_counter, create_histogram

    start_metrics_server(port=8001)
    messages = create_counter("messages_received_total", "Messages received")
    latency  = create_histogram("insert_latency_seconds", "Insert latency", buckets=[0.01, 0.1, 1.0])
"""

import os

from prometheus_client import Counter, Gauge, Histogram, start_http_server

# ── HTTP server ───────────────────────────────────────────────────────────────

_server_started: dict[int, bool] = {}


def start_metrics_server(port: int | None = None, env_var: str = "METRICS_PORT", default: int = 8000) -> None:
    """
    Start the Prometheus HTTP server on the given port.

    Port is resolved in order:
      1. Explicit port argument
      2. Environment variable (env_var)
      3. Default value

    Safe to call multiple times on the same port — only starts once per port.
    Runs in a background daemon thread; does not block the application.
    """
    resolved_port = port or int(os.environ.get(env_var, default))
    if _server_started.get(resolved_port):
        return
    start_http_server(resolved_port)
    _server_started[resolved_port] = True


# ── Metric factories ──────────────────────────────────────────────────────────

METRIC_PREFIX = "crypto_pipeline_"

_metric_cache: dict[str, object] = {}


def create_counter(name: str, description: str, labels: list[str] | None = None) -> Counter:
    """
    Create a Prometheus Counter with the crypto_pipeline_ prefix.

    Args:
        name:        Metric name without prefix. E.g. "messages_received_total"
        description: Human-readable description shown in /metrics output.
        labels:      Optional label names. E.g. ["service", "status"]

    Returns:
        Counter — same instance if called again with the same name.
    """
    full_name = f"{METRIC_PREFIX}{name}"
    if full_name not in _metric_cache:
        _metric_cache[full_name] = Counter(full_name, description, labelnames=labels or [])
    return _metric_cache[full_name]


def create_histogram(name: str, description: str, buckets: list[float], labels: list[str] | None = None) -> Histogram:
    """
    Create a Prometheus Histogram with the crypto_pipeline_ prefix.

    Args:
        name:        Metric name without prefix. E.g. "insert_latency_seconds"
        description: Human-readable description shown in /metrics output.
        buckets:     List of bucket boundaries. E.g. [0.01, 0.1, 0.5, 1.0]
        labels:      Optional label names.

    Returns:
        Histogram — same instance if called again with the same name.
    """
    full_name = f"{METRIC_PREFIX}{name}"
    if full_name not in _metric_cache:
        _metric_cache[full_name] = Histogram(full_name, description, buckets=buckets, labelnames=labels or [])
    return _metric_cache[full_name]


def create_gauge(name: str, description: str, labels: list[str] | None = None) -> Gauge:
    """
    Create a Prometheus Gauge with the crypto_pipeline_ prefix.

    Gauges track values that can go up and down — queue depth, active
    connections, memory usage. Unlike counters, gauges can be set, incremented,
    or decremented directly.

    Args:
        name:        Metric name without prefix. E.g. "rabbitmq_queue_depth"
        description: Human-readable description shown in /metrics output.
        labels:      Optional label names.

    Returns:
        Gauge — same instance if called again with the same name.
    """
    full_name = f"{METRIC_PREFIX}{name}"
    if full_name not in _metric_cache:
        _metric_cache[full_name] = Gauge(full_name, description, labelnames=labels or [])
    return _metric_cache[full_name]
