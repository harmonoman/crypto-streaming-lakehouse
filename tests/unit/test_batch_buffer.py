import threading
import time
from unittest.mock import MagicMock

import pytest

from consumer.batch_buffer import BatchBuffer


@pytest.fixture
def mock_repo():
    return MagicMock()


# Test 1 — size trigger flushes
def test_flush_on_batch_size(mock_repo):
    buf = BatchBuffer(mock_repo, batch_size=3, timeout_ms=10000)
    for i in range(3):
        buf.add({"trade_id": str(i)})
    mock_repo.insert_batch.assert_called_once()
    assert len(mock_repo.insert_batch.call_args[0][0]) == 3

# Test 2 — timeout trigger flushes
def test_flush_on_timeout(mock_repo):
    buf = BatchBuffer(mock_repo, batch_size=200, timeout_ms=100)
    buf.add({"trade_id": "x"})
    time.sleep(0.3)
    mock_repo.insert_batch.assert_called_once()

# Test 3 — no double flush under concurrent calls
def test_no_double_flush(mock_repo):
    buf = BatchBuffer(mock_repo, batch_size=200, timeout_ms=10000)
    buf.add({"trade_id": "x"})
    threads = [threading.Thread(target=buf.flush) for _ in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert mock_repo.insert_batch.call_count == 1

# Test 4 — failed insert returns batch to buffer
def test_failed_flush_returns_to_buffer(mock_repo):
    mock_repo.insert_batch.side_effect = Exception("DB down")
    buf = BatchBuffer(mock_repo, batch_size=200, timeout_ms=10000)
    buf.add({"trade_id": "abc"})
    buf.flush()
    assert len(buf.buffer) == 1   # message returned to buffer

# Test 5 — is_overloaded set correctly
def test_overload_flag(mock_repo):
    buf = BatchBuffer(mock_repo, batch_size=10, timeout_ms=10000)
    # Block flush from executing so buffer accumulates
    buf._flushing = True
    for i in range(21):
        buf.add({"trade_id": str(i)})
    assert buf.is_overloaded is True
    buf._flushing = False  # cleanup

# Test 6 — flush on empty buffer is a no-op
def test_flush_empty_buffer(mock_repo):
    buf = BatchBuffer(mock_repo, batch_size=10, timeout_ms=10000)
    buf.flush()
    mock_repo.insert_batch.assert_not_called()

# Test 7 — stop() cancels timer, no flush fires after shutdown
def test_stop_cancels_timer(mock_repo):
    buf = BatchBuffer(mock_repo, batch_size=200, timeout_ms=100)
    buf.stop()
    import time
    time.sleep(0.3)
    mock_repo.insert_batch.assert_not_called()
