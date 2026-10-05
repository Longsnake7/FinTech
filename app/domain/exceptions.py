"""Domain-level exceptions."""


class DomainError(Exception):
    """Base class for domain errors."""


class PaymentNotFoundError(DomainError):
    """Raised when a payment cannot be found."""

    def __init__(self, payment_id: str) -> None:
        self.payment_id = payment_id
        super().__init__(f"Payment {payment_id} not found")


class IdempotencyConflictError(DomainError):
    """Raised when an idempotency key is reused with a different payload."""

    def __init__(self, idempotency_key: str) -> None:
        self.idempotency_key = idempotency_key
        super().__init__(f"Idempotency key {idempotency_key} already used with a different request")


class PaymentGatewayError(DomainError):
    """Raised when payment gateway emulation fails."""


class WebhookDeliveryError(DomainError):
    """Raised when webhook notification fails."""


class UnknownEventMappingError(DomainError):
    """Raised when a broker message has no registered handler mapping."""

    def __init__(self, event_type: str) -> None:
        self.event_type = event_type
        super().__init__(f"No mapping for event type: {event_type}")
