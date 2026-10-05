"""Payment API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from app.api.deps import get_uow, require_api_key
from app.db.uow import UnitOfWork
from app.domain.exceptions import IdempotencyConflictError, PaymentNotFoundError
from app.schemas.payments import (
    ErrorResponse,
    PaymentAcceptedResponse,
    PaymentCreateRequest,
    PaymentResponse,
)
from app.services.payments import PaymentService

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "",
    response_model=PaymentAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        409: {"model": ErrorResponse, "description": "Idempotency key conflict"},
        422: {"description": "Validation error"},
    },
    summary="Create payment",
    description=(
        "Accepts a payment for asynchronous processing. "
        "Requires `Idempotency-Key` and `X-API-Key` headers. "
        "Persists the payment and an outbox event in one transaction."
    ),
)
async def create_payment(
    payload: PaymentCreateRequest,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=255,
            description="Unique key protecting against duplicate payment creation",
        ),
    ],
) -> PaymentAcceptedResponse:
    """Create a new payment or return the existing one for the same idempotency key."""
    service = PaymentService(uow)
    try:
        payment = await service.create_payment(payload, idempotency_key=idempotency_key)
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return PaymentAcceptedResponse(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        404: {"model": ErrorResponse, "description": "Payment not found"},
    },
    summary="Get payment",
    description="Returns detailed information about a payment by its ID.",
)
async def get_payment(
    payment_id: UUID,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    response: Response,
) -> PaymentResponse:
    """Fetch payment details."""
    del response  # reserved for future cache headers
    service = PaymentService(uow)
    try:
        payment = await service.get_payment(payment_id)
    except PaymentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return PaymentResponse.model_validate(payment)
