"""
tests/conftest.py

Shared pytest fixtures for the full test suite.

Scope decisions:
  - session scope for db_connection: creating a Postgres connection is
    expensive. One connection shared across the session is faster and
    sufficient since tests use transactions for isolation.
  - function scope for rabbitmq_channel: queues must be clean per test.
    Leftover messages from one test corrupt the next.
"""

import os
import pathlib

import pika
import psycopg2
import pytest


@pytest.fixture(scope="session")
def project_root():
    """Return the project root path for tests that need to reference files."""
    return pathlib.Path(__file__).parent.parent


@pytest.fixture(scope="session")
def db_connection():
    """
    Session-scoped Postgres connection for integration tests.

    Uses TEST_DATABASE_URL env var — falls back to a safe test default.
    Never connects to production. Closes connection after all tests finish.
    """
    url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://test_user:test_pass@localhost:5432/test_db",
    )
    conn = psycopg2.connect(url)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def rabbitmq_channel():
    """
    Function-scoped RabbitMQ channel for integration tests.

    Declares a temporary test queue and purges it after each test.
    Function scope ensures no messages leak between tests.
    """
    url = os.environ.get("TEST_AMQP_URL", "amqp://test_user:test_pass@localhost:5672/")
    connection = pika.BlockingConnection(pika.URLParameters(url))
    channel = connection.channel()

    queue_name = "test.queue"
    channel.queue_declare(queue=queue_name, durable=False)

    yield channel

    try:
        channel.queue_purge(queue=queue_name)
        channel.queue_delete(queue=queue_name)
    finally:
        connection.close()
