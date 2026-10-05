"""Tests for payment schemas and domain enums."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.enums import Currency, OutboxEventType, PaymentStatus
from app.schemas.payments import PaymentCreateRequest


def test_payment_create_request_valid() -> None:
    payload = PaymentCreateRequest(
        amount=Decimal("10.50"),
        currency=Currency.USD,
        description="Test payment",
        metadata={"order_id": "1"},
        webhook_url="https://example.com/webhook",
    )
    assert payload.amount == Decimal("10.50")
    assert payload.currency is Currency.USD


def test_payment_create_request_rejects_non_positive_amount() -> None:
    with pytest.raises(ValidationError):
        PaymentCreateRequest(
            amount=Decimal("0.00"),
            currency=Currency.RUB,
            webhook_url="https://example.com/webhook",
        )


def test_payment_create_request_rejects_too_many_decimals() -> None:
    with pytest.raises(ValidationError):
        PaymentCreateRequest(
            amount=Decimal("10.555"),
            currency=Currency.EUR,
            webhook_url="https://example.com/webhook",
        )


def test_domain_enums() -> None:
    assert PaymentStatus.PENDING.value == "pending"
    assert Currency.RUB.value == "RUB"
    assert OutboxEventType.PAYMENTS_NEW.value == "payments.new"
