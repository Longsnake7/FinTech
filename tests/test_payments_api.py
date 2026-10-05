"""API tests for payment endpoints."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.domain.enums import Currency, PaymentStatus
from app.domain.exceptions import IdempotencyConflictError, PaymentNotFoundError
from app.models import Payment


def _payment(**overrides) -> Payment:
    data = {
        "id": uuid4(),
        "amount": Decimal("10.00"),
        "currency": Currency.RUB,
        "description": "order",
        "payment_metadata": {},
        "status": PaymentStatus.PENDING,
        "idempotency_key": "key-1",
        "webhook_url": "https://example.com/hook",
        "created_at": datetime.now(UTC),
        "processed_at": None,
    }
    data.update(overrides)
    return Payment(**data)


@pytest.fixture
def auth_headers(settings) -> dict[str, str]:
    return {"X-API-Key": settings.api_key, "Idempotency-Key": "key-1"}


def test_create_payment_requires_api_key(client) -> None:
    response = client.post(
        "/api/v1/payments",
        json={
            "amount": "10.00",
            "currency": "USD",
            "description": "x",
            "metadata": {},
            "webhook_url": "https://example.com/hook",
        },
        headers={"Idempotency-Key": "key-1"},
    )
    assert response.status_code == 401


def test_create_payment_requires_idempotency_key(client, settings) -> None:
    response = client.post(
        "/api/v1/payments",
        json={
            "amount": "10.00",
            "currency": "USD",
            "description": "x",
            "metadata": {},
            "webhook_url": "https://example.com/hook",
        },
        headers={"X-API-Key": settings.api_key},
    )
    assert response.status_code == 422


def test_create_payment_validation_error(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/payments",
        json={
            "amount": "0",
            "currency": "USD",
            "webhook_url": "https://example.com/hook",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_payment_success(client, auth_headers) -> None:
    payment = _payment()
    with patch(
        "app.api.routers.payments.PaymentService.create_payment",
        new=AsyncMock(return_value=payment),
    ):
        response = client.post(
            "/api/v1/payments",
            json={
                "amount": "10.00",
                "currency": "RUB",
                "description": "order",
                "metadata": {},
                "webhook_url": "https://example.com/hook",
            },
            headers=auth_headers,
        )
    assert response.status_code == 202
    body = response.json()
    assert body["payment_id"] == str(payment.id)
    assert body["status"] == "pending"
    assert "created_at" in body


def test_create_payment_idempotency_conflict(client, auth_headers) -> None:
    with patch(
        "app.api.routers.payments.PaymentService.create_payment",
        new=AsyncMock(side_effect=IdempotencyConflictError("key-1")),
    ):
        response = client.post(
            "/api/v1/payments",
            json={
                "amount": "10.00",
                "currency": "RUB",
                "description": "order",
                "metadata": {},
                "webhook_url": "https://example.com/hook",
            },
            headers=auth_headers,
        )
    assert response.status_code == 409


def test_get_payment_success(client, settings) -> None:
    payment = _payment(status=PaymentStatus.SUCCEEDED)
    with patch(
        "app.api.routers.payments.PaymentService.get_payment",
        new=AsyncMock(return_value=payment),
    ):
        response = client.get(
            f"/api/v1/payments/{payment.id}",
            headers={"X-API-Key": settings.api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(payment.id)
    assert body["status"] == "succeeded"
    assert body["metadata"] == {}


def test_get_payment_not_found(client, settings) -> None:
    payment_id = uuid4()
    with patch(
        "app.api.routers.payments.PaymentService.get_payment",
        new=AsyncMock(side_effect=PaymentNotFoundError(str(payment_id))),
    ):
        response = client.get(
            f"/api/v1/payments/{payment_id}",
            headers={"X-API-Key": settings.api_key},
        )
    assert response.status_code == 404
