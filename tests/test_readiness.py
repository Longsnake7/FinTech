"""Readiness endpoint tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_session_factory
from app.main import create_app


@pytest.fixture
def ready_client(settings):
    app = create_app(settings)
    session = AsyncMock()
    session.execute = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    factory = MagicMock(return_value=session)

    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as client:
        yield client


def test_readiness_ok(ready_client) -> None:
    response = ready_client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}
