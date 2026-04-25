"""
dags/dag_callbacks.py

Airflow DAG callbacks for structured observability logging.

Why callbacks instead of manual logging inside tasks?
    Callbacks are called by Airflow automatically on task/DAG state changes.
    This means failures are logged even if the task itself crashes before
    reaching any logging code — the callback always fires.

Why structured logs instead of alerts?
    For MVP, structured JSON logs are sufficient. They are machine-readable
    and can be consumed by any log aggregator (Elasticsearch, CloudWatch,
    Datadog) without any additional integration. Alerts (Slack, email) can
    be added later by adding one line to these callbacks.

Why extra={} on every log call?
    The extra dict becomes top-level fields in the JSON log output.
    Without it, dag_id/task_id/run_id would be buried in the message string
    and impossible to query or filter on in a log aggregator.
"""

from shared.logger import get_logger

logger = get_logger("airflow")


def on_task_failure(context: dict) -> None:
    """
    Called by Airflow when any task fails.
    Emits a structured ERROR log with task identity and exception details.

    Wired into default_args["on_failure_callback"] so it applies to all tasks.
    """
    dag_id  = context["dag"].dag_id
    task_id = context["task_instance"].task_id
    run_id  = context["run_id"]
    exc     = context.get("exception")

    logger.error(
        "DAG task failed",
        extra={
            "dag_id":    dag_id,
            "task_id":   task_id,
            "run_id":    run_id,
            "exception": str(exc),
        },
    )


def on_dag_success(context: dict) -> None:
    """
    Called by Airflow when the full DAG run completes successfully.
    Emits a structured INFO log with run identity and wall-clock duration.

    Duration tracking enables SLA monitoring — alert if duration_s > threshold.
    """
    dag_id     = context["dag"].dag_id
    run_id     = context["run_id"]
    start_date = context["dag_run"].start_date
    end_date   = context["dag_run"].end_date

    duration_s = (end_date - start_date).total_seconds() if end_date else None

    logger.info(
        "DAG run complete",
        extra={
            "dag_id":     dag_id,
            "run_id":     run_id,
            "duration_s": duration_s,
        },
    )
