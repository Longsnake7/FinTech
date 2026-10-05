"""Retry delay calculation tests."""

from app.messaging.retry import compute_retry_delay


def test_exponential_backoff_without_jitter(settings) -> None:
    settings.retry_base_delay_seconds = 1.0
    settings.retry_max_delay_seconds = 30.0
    settings.retry_jitter_seconds = 0.0

    assert compute_retry_delay(1, settings, uniform=lambda _a, _b: 0.0) == 1.0
    assert compute_retry_delay(2, settings, uniform=lambda _a, _b: 0.0) == 2.0
    assert compute_retry_delay(3, settings, uniform=lambda _a, _b: 0.0) == 4.0


def test_backoff_is_capped(settings) -> None:
    settings.retry_base_delay_seconds = 10.0
    settings.retry_max_delay_seconds = 15.0
    settings.retry_jitter_seconds = 0.0

    assert compute_retry_delay(3, settings, uniform=lambda _a, _b: 0.0) == 15.0


def test_jitter_is_added(settings) -> None:
    settings.retry_base_delay_seconds = 1.0
    settings.retry_max_delay_seconds = 30.0
    settings.retry_jitter_seconds = 0.5

    delay = compute_retry_delay(1, settings, uniform=lambda _a, _b: 0.25)
    assert delay == 1.25
