"""Retry delay helpers with exponential backoff and jitter."""

from __future__ import annotations

import random
from collections.abc import Callable

from app.config import Settings

UniformFn = Callable[[float, float], float]


def compute_retry_delay(
    attempt: int,
    settings: Settings,
    *,
    uniform: UniformFn | None = None,
) -> float:
    """
    Compute delay before the next processing attempt.

    attempt is the failed attempt number (1-based): after attempt 1 fails,
    delay before attempt 2 uses attempt=1.
    """
    if attempt < 1:
        msg = "attempt must be >= 1"
        raise ValueError(msg)

    uniform_fn = uniform or random.uniform
    exponential = settings.retry_base_delay_seconds * (2 ** (attempt - 1))
    capped = min(exponential, settings.retry_max_delay_seconds)
    jitter = uniform_fn(0.0, settings.retry_jitter_seconds)
    return capped + jitter
