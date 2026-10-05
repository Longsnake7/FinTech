"""FastAPI dependency providers."""

from collections.abc import AsyncIterator, Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.db.uow import UnitOfWork


def get_engine(settings: Annotated[Settings, Depends(get_settings)]) -> AsyncEngine:
    """Resolve the application engine from app.state via dependency override later."""
    raise RuntimeError("Engine dependency must be overridden in application factory")


def get_session_factory(
    engine: Annotated[AsyncEngine, Depends(get_engine)],
) -> async_sessionmaker[AsyncSession]:
    """Build session factory from engine (overridden in app factory)."""
    raise RuntimeError("Session factory dependency must be overridden in application factory")


async def get_uow(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AsyncIterator[UnitOfWork]:
    """Provide a Unit of Work bound to a request."""
    async with UnitOfWork(session_factory) as uow:
        yield uow


def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """Validate static API key for protected endpoints."""
    if x_api_key is None or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


def create_uow_dependency(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], AsyncIterator[UnitOfWork]]:
    """Create a UnitOfWork dependency closure bound to a session factory."""

    async def _dependency() -> AsyncIterator[UnitOfWork]:
        async with UnitOfWork(session_factory) as uow:
            yield uow

    return _dependency
