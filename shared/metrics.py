"""
shared/metrics.py

Shared Prometheus HTTP server startup utility.
Each service (producer, consumer) calls start_metrics_server() once at startup
with its own port. Service-specific counters and histograms live in each
service's own metrics.py.

Usage:
    from shared.metrics import start_metrics_server
    start_metrics_server(port=8001)
"""

import os

from prometheus_client import start_http_server

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
