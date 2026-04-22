"""
consumer/batch_buffer.py

Thread-safe buffer that collects messages and flushes them to the database
in batches, triggered by size or time — whichever comes first.

Why batching:
    Individual inserts (1 message = 1 DB round trip) are slow under load.
    Batching amortizes the round-trip cost: 200 messages = 1 DB insert.

Why a lock:
    The consumer thread calls add() continuously. The timer thread calls
    flush() on a schedule. Without a lock, both threads could read/write
    self.buffer simultaneously, corrupting its contents.

Why we release the lock before the DB call:
    Holding a lock during a slow operation (DB insert) blocks add() for
    the entire duration, creating a bottleneck. We copy the buffer under
    the lock, release it immediately, then do the DB work freely.

Why _flushing flag:
    Prevents a double-flush race condition when both the timer and a
    size trigger fire at nearly the same time.

Usage:
    from consumer.batch_buffer import BatchBuffer

    buffer = BatchBuffer(repository=repo, batch_size=200, timeout_ms=2000)
    buffer.add(message_dict)   # called per message in on_message
    buffer.flush()             # called on shutdown to drain remaining messages
    buffer.stop()              # cancel pending timer on shutdown
"""

import threading

from shared.logger import get_logger

logger = get_logger("consumer")


class BatchBuffer:
    """
    Collects trade messages and flushes them to Postgres in batches.

    Flush is triggered by:
      - Size: when buffer reaches batch_size
      - Time: when timeout_ms elapses since last flush

    is_overloaded is set True when buffer exceeds 2 * batch_size,
    signalling the consumer to pause ingestion temporarily.
    """

    def __init__(self, repository, batch_size: int = 200, timeout_ms: int = 2000) -> None:
        self.repository = repository
        self.batch_size = batch_size
        self.timeout_s = timeout_ms / 1000

        self.buffer: list[dict] = []
        self.lock = threading.Lock()
        self.is_overloaded = False

        # Guards against concurrent flushes from timer + size trigger firing together.
        self._flushing = False

        self._timer: threading.Timer | None = None
        self._start_timer()

    # ── Public API ────────────────────────────────────────────────────────────

    def add(self, message: dict) -> None:
        """
        Add a message to the buffer.

        Triggers a flush if the buffer reaches batch_size.
        Sets is_overloaded if the buffer exceeds 2 * batch_size.
        """
        with self.lock:
            self.buffer.append(message)
            size = len(self.buffer)
            self.is_overloaded = size > 2 * self.batch_size

        if size >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        """
        Flush the current buffer to the database.

        Acquires the lock only to copy and clear the buffer — not during
        the DB insert — so add() is never blocked by a slow write.

        If the DB insert fails, the batch is returned to the front of the
        buffer so it will be retried on the next flush.
        """
        with self.lock:
            # Prevent concurrent flushes from timer and size trigger racing.
            if self._flushing or not self.buffer:
                return
            self._flushing = True
            batch = self.buffer.copy()
            self.buffer.clear()
            self.is_overloaded = False

        try:
            self.repository.insert_batch(batch)
            logger.info("Batch flushed", extra={"count": len(batch)})
        except Exception as exc:
            # On failure, return the batch to the front of the buffer
            # so the next flush attempt retries it. No data is lost.
            logger.error(
                "Batch flush failed — returning batch to buffer",
                extra={"count": len(batch), "error": str(exc)},
            )
            with self.lock:
                self.buffer = batch + self.buffer
        finally:
            with self.lock:
                self._flushing = False
            self._reset_timer()

    def stop(self) -> None:
        """
        Cancel the pending timer. Call on shutdown after a final flush().
        """
        with self.lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def insert_one(self, message: dict) -> None:
        """Thin wrapper so BatchBuffer can be used as a drop-in for repository."""
        self.add(message)

    # ── Timer management ──────────────────────────────────────────────────────

    def _start_timer(self) -> None:
        """Start a one-shot timer that calls flush() after timeout_s."""
        self._timer = threading.Timer(self.timeout_s, self.flush)
        self._timer.daemon = True   # timer thread won't prevent process exit
        self._timer.start()

    def _reset_timer(self) -> None:
        """Cancel the current timer and start a fresh one."""
        with self.lock:
            if self._timer is not None:
                self._timer.cancel()
            self._start_timer()
