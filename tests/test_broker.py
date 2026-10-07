"""Broker topology declaration tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings
from app.messaging.broker import declare_topology


@pytest.mark.asyncio
async def test_declare_topology_binds_queues(settings: Settings) -> None:
    broker = MagicMock()
    exchange = AsyncMock()
    queue = AsyncMock()
    queue.bind = AsyncMock()
    broker.declare_exchange = AsyncMock(return_value=exchange)
    broker.declare_queue = AsyncMock(return_value=queue)

    await declare_topology(broker, settings)

    assert broker.declare_exchange.await_count == 1
    assert broker.declare_queue.await_count == 3
    assert queue.bind.await_count == 3
