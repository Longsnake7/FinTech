"""RabbitMQ topology constants and builders."""

from __future__ import annotations

from faststream.rabbit import ExchangeType, RabbitExchange, RabbitQueue

from app.config import Settings


def build_exchange(settings: Settings) -> RabbitExchange:
    """Create the main payments topic exchange."""
    return RabbitExchange(
        settings.rabbitmq_exchange,
        type=ExchangeType.TOPIC,
        durable=True,
    )


def build_payments_new_queue(settings: Settings) -> RabbitQueue:
    """Main processing queue for new payment events."""
    return RabbitQueue(
        settings.rabbitmq_queue_payments_new,
        durable=True,
        routing_key=settings.rabbitmq_routing_payments_new,
    )


def build_retry_queue(settings: Settings) -> RabbitQueue:
    """
    Retry holding queue.

    Messages expire via per-message TTL and are dead-lettered back to the
    main exchange with payments.new routing key, surviving consumer restarts.
    """
    return RabbitQueue(
        settings.rabbitmq_queue_retry,
        durable=True,
        routing_key=settings.rabbitmq_routing_retry,
        arguments={
            "x-dead-letter-exchange": settings.rabbitmq_exchange,
            "x-dead-letter-routing-key": settings.rabbitmq_routing_payments_new,
        },
    )


def build_dlq_queue(settings: Settings) -> RabbitQueue:
    """Dead letter queue for exhausted or unmapped messages."""
    return RabbitQueue(
        settings.rabbitmq_queue_dlq,
        durable=True,
        routing_key=settings.rabbitmq_routing_dlq,
    )
