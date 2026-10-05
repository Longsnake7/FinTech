"""Runnable consumer entrypoint without FastStream CLI extras."""

from __future__ import annotations

import asyncio
import logging

from app.workers.consumer_app import app

logger = logging.getLogger(__name__)


def main() -> None:
    """Start the FastStream consumer application."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting payment consumer")
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
