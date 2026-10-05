"""RabbitMQ broker factory and declaration helpers."""

from __future__ import annotations

from faststream.rabbit import RabbitBroker

from app.config import Settings
from app.messaging.topology import (
    build_dlq_queue,
    build_exchange,
    build_payments_new_queue,
    build_retry_queue,
)


def create_broker(settings: Settings) -> RabbitBroker:
    """Create a configured RabbitBroker instance."""
    return RabbitBroker(settings.rabbitmq_amqp_url)


async def declare_topology(broker: RabbitBroker, settings: Settings) -> None:
    """Declare exchange, queues and bindings used by the service."""
    exchange = await broker.declare_exchange(build_exchange(settings))
    queue_new = await broker.declare_queue(build_payments_new_queue(settings))
    queue_retry = await broker.declare_queue(build_retry_queue(settings))
    queue_dlq = await broker.declare_queue(build_dlq_queue(settings))

    await queue_new.bind(exchange, routing_key=settings.rabbitmq_routing_payments_new)
    await queue_retry.bind(exchange, routing_key=settings.rabbitmq_routing_retry)
    await queue_dlq.bind(exchange, routing_key=settings.rabbitmq_routing_dlq)
