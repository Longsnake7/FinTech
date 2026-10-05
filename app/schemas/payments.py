"""Pydantic schemas for payment API and internal transfers."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import Currency, PaymentStatus


class PaymentCreateRequest(BaseModel):
    """Request body for creating a payment."""

    amount: Decimal = Field(..., gt=0, decimal_places=2, examples=["100.00"])
    currency: Currency
    description: str = Field(default="", max_length=1024)
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: AnyHttpUrl

    @field_validator("amount")
    @classmethod
    def amount_must_have_two_decimals(cls, value: Decimal) -> Decimal:
        """Normalize amount to two decimal places."""
        quantized = value.quantize(Decimal("0.01"))
        if quantized != value:
            msg = "amount must have at most 2 decimal places"
            raise ValueError(msg)
        return quantized


class PaymentAcceptedResponse(BaseModel):
    """Response returned after accepting a payment for processing."""

    model_config = ConfigDict(from_attributes=True)

    payment_id: UUID
    status: PaymentStatus
    created_at: datetime


class PaymentResponse(BaseModel):
    """Full payment representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict[str, Any] = Field(validation_alias="payment_metadata")
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None = None


class ErrorResponse(BaseModel):
    """Standard API error payload."""

    detail: str
