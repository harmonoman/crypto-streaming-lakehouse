"""
producer/utils.py

Small pure utility functions for the producer.
No side effects, no I/O, no logging.
"""


def exponential_backoff(attempt: int, base: int = 1, max_delay: int = 60) -> int:
    """
    Return the retry delay in seconds for a given attempt number.

    Delay doubles on each attempt, capped at max_delay.

    Examples:
        attempt=0 → 1s
        attempt=1 → 2s
        attempt=2 → 4s
        attempt=3 → 8s
        attempt=6 → 60s (capped)

    Args:
        attempt:   Zero-based attempt number. Must be >= 0.
        base:      Starting delay in seconds. Default: 1.
        max_delay: Maximum delay in seconds. Default: 60.

    Returns:
        Delay in whole seconds (int).

    Raises:
        ValueError: If attempt is negative.
    """
    if attempt < 0:
        raise ValueError(f"attempt must be >= 0, got {attempt}")

    delay = base * (2 ** attempt)
    return min(int(delay), max_delay)
