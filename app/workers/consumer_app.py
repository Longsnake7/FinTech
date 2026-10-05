"""Consumer application entrypoint (FastStream + payment processing)."""

from __future__ import annotations

import logging
from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitBroker

from app.config import Settings, get_settings
from app.db.session import create_engine, create_session_factory
from app.messaging.broker import create_broker, declare_topology
from app.messaging.consumer import MessageConsumerHandler
from app.messaging.publisher import RabbitMessagePublisher
from app.messaging.topology import build_exchange, build_payments_new_queue
from app.services.gateway import PaymentGateway
from app.services.processor import PaymentProcessor, create_uow_factory
from app.services.webhook import WebhookClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_consumer_app(settings: Settings | None = None) -> tuple[FastStream, RabbitBroker]:
    """Build FastStream consumer application."""
    cfg = settings or get_settings()
    engine = create_engine(cfg)
    session_factory = create_session_factory(engine)
    uow_factory = create_uow_factory(session_factory)

    broker = create_broker(cfg)
    publisher = RabbitMessagePublisher(broker, cfg)
    gateway = PaymentGateway(cfg)
    webhook_client = WebhookClient(cfg)
    processor = PaymentProcessor(
        uow_factory=uow_factory,
        gateway=gateway,
        webhook_client=webhook_client,
    )
    handler = MessageConsumerHandler(
        settings=cfg,
        processor=processor,
        publisher=publisher,
    )

    exchange = build_exchange(cfg)
    queue = build_payments_new_queue(cfg)

    @broker.subscriber(queue, exchange)
    async def on_payments_new(message: dict[str, Any]) -> None:
        await handler.handle(message)

    app = FastStream(broker)

    @app.after_startup
    async def on_startup() -> None:
        await declare_topology(broker, cfg)
        logger.info("Consumer topology declared")

    @app.on_shutdown
    async def on_shutdown() -> None:
        await webhook_client.__aexit__(None, None, None)
        await engine.dispose()
        logger.info("Consumer shut down")

    return app, broker


settings = get_settings()
app, broker = create_consumer_app(settings)
