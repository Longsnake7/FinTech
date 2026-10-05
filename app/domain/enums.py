"""Domain enums and shared constants."""

from enum import StrEnum


class PaymentStatus(StrEnum):
    """Lifecycle status of a payment."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Currency(StrEnum):
    """Supported payment currencies."""

    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class OutboxStatus(StrEnum):
    """Delivery status of an outbox event."""

    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"


class OutboxEventType(StrEnum):
    """Known outbox / RabbitMQ event types."""

    PAYMENTS_NEW = "payments.new"
