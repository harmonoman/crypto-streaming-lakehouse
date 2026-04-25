"""
tests/unit/test_dag_callbacks.py

Unit tests for on_task_failure() and on_dag_success() callbacks
in dags/dag_callbacks.py.

Airflow context is simulated with MagicMock — no live Airflow required.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from dag_callbacks import on_dag_success, on_task_failure


def _make_failure_context(dag_id="crypto_pipeline", task_id="dbt_run",
                           run_id="run_001", exc="Something broke"):
    return {
        "dag":           MagicMock(dag_id=dag_id),
        "task_instance": MagicMock(task_id=task_id),
        "run_id":        run_id,
        "exception":     exc,
        "dag_run":       MagicMock(start_date=None, end_date=None),
    }


def _make_success_context(dag_id="crypto_pipeline", run_id="run_001"):
    return {
        "dag":     MagicMock(dag_id=dag_id),
        "run_id":  run_id,
        "dag_run": MagicMock(
            start_date=datetime(2026, 4, 24, 15, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 4, 24, 15, 0, 42, tzinfo=UTC),
        ),
    }


# ── Test 1 — Failure callback logs error ─────────────────────────────────────

def test_on_task_failure_logs_error():
    ctx = _make_failure_context()
    with patch("dag_callbacks.logger") as mock_logger:
        on_task_failure(ctx)
    mock_logger.error.assert_called_once()
    call_kwargs = mock_logger.error.call_args
    assert call_kwargs[0][0] == "DAG task failed"
    extra = call_kwargs[1]["extra"]
    assert "dag_id"    in extra
    assert "task_id"   in extra
    assert "run_id"    in extra
    assert "exception" in extra


# ── Test 2 — Success callback logs info ──────────────────────────────────────

def test_on_dag_success_logs_info():
    ctx = _make_success_context()
    with patch("dag_callbacks.logger") as mock_logger:
        on_dag_success(ctx)
    mock_logger.info.assert_called_once()
    call_kwargs = mock_logger.info.call_args
    assert call_kwargs[0][0] == "DAG run complete"
    extra = call_kwargs[1]["extra"]
    assert "dag_id"     in extra
    assert "run_id"     in extra
    assert "duration_s" in extra


# ── Test 3 — Duration computed correctly ─────────────────────────────────────

def test_on_dag_success_computes_duration():
    ctx = _make_success_context()
    with patch("dag_callbacks.logger") as mock_logger:
        on_dag_success(ctx)
    extra = mock_logger.info.call_args[1]["extra"]
    assert extra["duration_s"] == 42.0


# ── Test 4 — Uses shared logger ───────────────────────────────────────────────

def test_callbacks_use_shared_logger():
    from pathlib import Path
    source = Path("dags/dag_callbacks.py").read_text()
    assert 'get_logger("airflow")' in source
    assert "from shared.logger import get_logger" in source


# ── Test 5 — default_args wired correctly ────────────────────────────────────

def test_default_args_has_failure_callback():
    from pathlib import Path
    source = Path("dags/crypto_pipeline_dag.py").read_text()
    assert "on_failure_callback" in source
    assert "on_task_failure"     in source


# ── Test 6 — Handles missing end_date gracefully ─────────────────────────────

def test_on_dag_success_handles_missing_end_date():
    ctx = _make_success_context()
    ctx["dag_run"].end_date = None
    with patch("dag_callbacks.logger") as mock_logger:
        on_dag_success(ctx)
    extra = mock_logger.info.call_args[1]["extra"]
    assert extra["duration_s"] is None
