"""Application factory and ASGI entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.deps import get_engine, get_session_factory
from app.api.routers import health
from app.config import Settings, get_settings
from app.db.session import create_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    cfg = settings or get_settings()
    engine = create_engine(cfg)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        _app.state.settings = cfg
        _app.state.engine = engine
        _app.state.session_factory = session_factory
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title="Payment Service",
        description="Asynchronous payment processing microservice",
        version="0.1.0",
        lifespan=lifespan,
    )

    def _get_engine() -> AsyncEngine:
        return engine

    def _get_session_factory() -> async_sessionmaker[AsyncSession]:
        return session_factory

    app.dependency_overrides[get_engine] = _get_engine
    app.dependency_overrides[get_session_factory] = _get_session_factory
    app.dependency_overrides[get_settings] = lambda: cfg

    app.include_router(health.router)

    return app


app = create_app()
