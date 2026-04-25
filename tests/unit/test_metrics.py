"""
tests/unit/test_metrics.py

Unit tests for shared/metrics.py — metric factory functions.
Written BEFORE implementation (TDD).
"""

import contextlib

from prometheus_client import REGISTRY, Counter, Gauge, Histogram

from shared.metrics import METRIC_PREFIX, create_counter, create_gauge, create_histogram


def _unregister(name):
    """Helper to clean up metrics between tests."""
    full_name = f"crypto_pipeline_{name}"
    collectors = list(REGISTRY._names_to_collectors.keys())
    for key in collectors:
        if full_name in key:
            with contextlib.suppress(Exception):
                REGISTRY.unregister(REGISTRY._names_to_collectors[key])
            break


def test_create_counter_returns_counter_instance():
    _unregister("test_counter_t1_total")
    counter = create_counter("test_counter_t1_total", "A test counter")
    assert isinstance(counter, Counter)
    _unregister("test_counter_t1_total")


def test_create_counter_has_correct_prefix():
    counter = create_counter("t2_counter_total", "A test counter")
    assert counter._name.startswith("crypto_pipeline_")
    assert "crypto_pipeline_t2_counter" in counter._name


def test_create_histogram_returns_histogram_instance():
    _unregister("test_latency_t1_seconds")
    hist = create_histogram("test_latency_t1_seconds", "A test histogram", buckets=[0.1, 0.5, 1.0])
    assert isinstance(hist, Histogram)
    _unregister("test_latency_t1_seconds")


def test_create_histogram_has_correct_prefix():
    _unregister("test_latency_t2_seconds")
    hist = create_histogram("test_latency_t2_seconds", "A test histogram", buckets=[0.1, 0.5])
    assert "crypto_pipeline_test_latency_t2_seconds" in hist._name
    _unregister("test_latency_t2_seconds")


def test_create_counter_with_labels():
    _unregister("test_labeled_t1_total")
    counter = create_counter("test_labeled_t1_total", "Labeled counter", labels=["service"])
    counter.labels(service="producer").inc()
    _unregister("test_labeled_t1_total")


def test_all_metrics_start_with_prefix():
    assert METRIC_PREFIX == "crypto_pipeline_"
    _unregister("prefix_check_total")
    c = create_counter("prefix_check_total", "desc")
    assert c._name.startswith("crypto_pipeline_")
    _unregister("prefix_check_total")


def test_create_counter_duplicate_does_not_crash():
    _unregister("test_dedup_total")
    create_counter("test_dedup_total", "First registration")
    create_counter("test_dedup_total", "Second registration")
    _unregister("test_dedup_total")


# ── Gauge creation ────────────────────────────────────────────────────────────

def test_create_gauge_returns_gauge_instance():
    gauge = create_gauge("t11_queue_depth", "A test gauge")
    assert isinstance(gauge, Gauge)


def test_create_gauge_has_correct_prefix():
    gauge = create_gauge("t12_queue_depth", "A test gauge")
    assert gauge._name.startswith("crypto_pipeline_")


def test_create_gauge_duplicate_returns_same_instance():
    g1 = create_gauge("t13_queue_depth", "First call")
    g2 = create_gauge("t13_queue_depth", "Second call")
    assert g1 is g2
