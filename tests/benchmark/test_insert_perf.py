"""
tests/benchmark/test_insert_perf.py

Performance benchmark: single-row inserts vs batch inserts.

This is a development tool — not a pytest test suite.
Run directly:

    python tests/benchmark/test_insert_perf.py

Requirements:
    - Postgres running (docker compose up -d)
    - Migrations applied (python infra/migrate.py)
    - DATABASE_URL set in environment
"""

import os
import time

import psycopg2

from consumer.repository import TradeRepository

RUNS = 3       # number of timed runs per strategy — results are averaged
N    = 1000    # rows per run


# ── Test data ─────────────────────────────────────────────────────────────────

def generate_data(n: int, prefix: str = "bench") -> list[dict]:
    """Generate n fake trade messages with unique trade_ids."""
    return [
        {
            "trade_id": f"{prefix}_{i}",
            "price": "100.00",
            "size": "0.01",
            "side": "buy",
            "time": "2024-01-01T00:00:00Z",
        }
        for i in range(n)
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────

def truncate(conn: psycopg2.extensions.connection) -> None:
    """Clear the table to ensure a clean state before each run."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE bronze.raw_trades;")
    conn.commit()


def safe_throughput(n: int, elapsed: float) -> float:
    """Rows per second — guarded against near-zero elapsed time."""
    return n / elapsed if elapsed > 0 else float("inf")


# ── Benchmarks ────────────────────────────────────────────────────────────────

def benchmark_single(repository: TradeRepository, data: list[dict]) -> tuple[float, float]:
    """Insert rows one at a time. Returns (elapsed_seconds, rows_per_sec)."""
    start = time.perf_counter()
    for row in data:
        repository.insert_one(row)
    elapsed = time.perf_counter() - start
    return elapsed, safe_throughput(len(data), elapsed)


def benchmark_batch(repository: TradeRepository, data: list[dict]) -> tuple[float, float]:
    """Insert all rows in a single batch call. Returns (elapsed_seconds, rows_per_sec)."""
    start = time.perf_counter()
    repository.insert_batch(data)
    elapsed = time.perf_counter() - start
    return elapsed, safe_throughput(len(data), elapsed)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    repo = TradeRepository(conn)

    print(f"\nBenchmark: {N} rows × {RUNS} runs — single insert vs batch insert")
    print("=" * 58)

    # Warm-up: exercise the full insert path once before timing anything.
    # This avoids counting connection/cache cold-start latency as insert time.
    print("\nWarming up...")
    truncate(conn)
    repo.insert_one(generate_data(1)[0])
    truncate(conn)

    # ── Single insert ──────────────────────────────────────────────────────────
    single_times = []
    for run in range(1, RUNS + 1):
        truncate(conn)
        data = generate_data(N, prefix=f"single_run{run}")
        elapsed, _ = benchmark_single(repo, data)
        single_times.append(elapsed)
        print(f"  Single run {run}: {elapsed:.3f}s")

    single_avg = sum(single_times) / len(single_times)
    single_throughput = safe_throughput(N, single_avg)

    print(f"\nSingle Insert (avg of {RUNS} runs):")
    print(f"  Time:       {single_avg:.3f}s")
    print(f"  Throughput: {single_throughput:,.0f} rows/sec")

    # ── Batch insert ───────────────────────────────────────────────────────────
    batch_times = []
    for run in range(1, RUNS + 1):
        truncate(conn)
        data = generate_data(N, prefix=f"batch_run{run}")
        elapsed, _ = benchmark_batch(repo, data)
        batch_times.append(elapsed)
        print(f"  Batch  run {run}: {elapsed:.3f}s")

    batch_avg = sum(batch_times) / len(batch_times)
    batch_throughput = safe_throughput(N, batch_avg)

    print(f"\nBatch Insert (avg of {RUNS} runs):")
    print(f"  Time:       {batch_avg:.3f}s")
    print(f"  Throughput: {batch_throughput:,.0f} rows/sec")

    # ── Summary ────────────────────────────────────────────────────────────────
    speedup = single_avg / batch_avg if batch_avg > 0 else float("inf")
    print(f"\nResult: batch insert is {speedup:.1f}x faster than single inserts")
    print("=" * 58)

    truncate(conn)   # clean up after benchmark
    conn.close()


if __name__ == "__main__":
    main()
