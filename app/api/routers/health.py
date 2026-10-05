"""Health and readiness endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_session_factory

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict[str, str]:
    """Liveness probe that does not touch external dependencies."""
    return {"status": "ok"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> dict[str, Any]:
    """Readiness probe verifying PostgreSQL connectivity."""
    async with session_factory() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}
