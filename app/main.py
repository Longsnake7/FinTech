"""Application factory and ASGI entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.deps import get_engine, get_session_factory
from app.api.routers import health, payments
from app.config import Settings, get_settings
from app.db.session import create_engine, create_session_factory
from app.messaging.broker import create_broker, declare_topology
from app.messaging.outbox_worker import OutboxWorker
from app.messaging.publisher import RabbitMessagePublisher
from app.services.processor import create_uow_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    cfg = settings or get_settings()
    engine = create_engine(cfg)
    session_factory = create_session_factory(engine)
    uow_factory = create_uow_factory(session_factory)

    broker = create_broker(cfg)
    publisher = RabbitMessagePublisher(broker, cfg)
    outbox_worker = OutboxWorker(
        settings=cfg,
        uow_factory=uow_factory,
        publisher=publisher,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        import asyncio

        _app.state.settings = cfg
        _app.state.engine = engine
        _app.state.session_factory = session_factory
        _app.state.broker = broker
        _app.state.outbox_worker = outbox_worker

        worker_task: asyncio.Task[None] | None = None
        try:
            if cfg.outbox_worker_enabled:
                await broker.connect()
                await declare_topology(broker, cfg)
                worker_task = asyncio.create_task(outbox_worker.run_forever())
            yield
        finally:
            outbox_worker.stop()
            if worker_task is not None:
                await worker_task
            await broker.close()
            await engine.dispose()

    app = FastAPI(
        title="Payment Service",
        description=(
            "Asynchronous payment processing microservice. "
            "Accepts payments via REST API, stores them in PostgreSQL, "
            "publishes events through a transactional outbox to RabbitMQ, "
            "and processes them with a dedicated consumer (gateway emulation + webhook)."
        ),
        version="1.0.0",
        lifespan=lifespan,
        openapi_tags=[
            {
                "name": "payments",
                "description": "Create and query payments (requires `X-API-Key`).",
            },
            {
                "name": "health",
                "description": "Liveness and readiness probes for orchestration.",
            },
        ],
    )

    def _get_engine() -> AsyncEngine:
        return engine

    def _get_session_factory() -> async_sessionmaker[AsyncSession]:
        return session_factory

    app.dependency_overrides[get_engine] = _get_engine
    app.dependency_overrides[get_session_factory] = _get_session_factory
    app.dependency_overrides[get_settings] = lambda: cfg

    app.include_router(health.router)
    app.include_router(payments.router, prefix=cfg.api_prefix)

    return app


app = create_app()
