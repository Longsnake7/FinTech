"""Worker entrypoint smoke tests."""

from app.config import Settings
from app.workers import consumer_app


def test_create_consumer_app(settings: Settings) -> None:
    app, broker = consumer_app.create_consumer_app(settings)
    assert app is not None
    assert broker is not None


def test_run_consumer_main_importable() -> None:
    from app.workers import run_consumer

    assert callable(run_consumer.main)
