"""Consumer orchestration: mapping, retry, DLQ."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.config import Settings
from app.domain.exceptions import UnknownEventMappingError
from app.messaging.publisher import MessagePublisher
from app.messaging.retry import compute_retry_delay
from app.schemas.payments import DlqMessage
from app.services.processor import PaymentProcessor

logger = logging.getLogger(__name__)


class MessageConsumerHandler:
    """
    Processes inbound broker messages.

    On success: completes.
    On unknown mapping: sends to DLQ.
    On processing error: republishes to retry queue with backoff, or DLQ after max attempts.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        processor: PaymentProcessor,
        publisher: MessagePublisher,
    ) -> None:
        self._settings = settings
        self._processor = processor
        self._publisher = publisher

    async def handle(self, payload: dict[str, Any]) -> None:
        """Handle a single decoded message payload."""
        attempt = int(payload.get("attempt", 1))
        event_id = str(payload.get("event_id", ""))
        try:
            await self._processor.process(payload)
        except UnknownEventMappingError as exc:
            logger.warning("No mapping for message %s: %s", event_id, exc)
            await self._send_dlq(payload, error=str(exc), attempts=attempt, reason="no_mapping")
        except Exception as exc:
            logger.exception("Processing failed for message %s (attempt %s)", event_id, attempt)
            if attempt >= self._settings.message_max_attempts:
                await self._send_dlq(
                    payload,
                    error=str(exc),
                    attempts=attempt,
                    reason="max_attempts_exceeded",
                )
                payment_id = payload.get("payment_id")
                if payment_id:
                    await self._processor.mark_payment_failed(UUID(str(payment_id)))
            else:
                delay = compute_retry_delay(attempt, self._settings)
                next_payload = {**payload, "attempt": attempt + 1}
                await self._publisher.publish_retry(
                    next_payload,
                    message_id=event_id or "unknown",
                    delay_seconds=delay,
                )

    async def _send_dlq(
        self,
        payload: dict[str, Any],
        *,
        error: str,
        attempts: int,
        reason: str,
    ) -> None:
        dlq = DlqMessage(
            original_event=payload,
            error=error,
            attempts=attempts,
            failed_at=datetime.now(UTC),
            reason=reason,
        )
        message_id = str(payload.get("event_id", "unknown"))
        await self._publisher.publish_dlq(
            dlq.model_dump(mode="json"),
            message_id=f"dlq-{message_id}",
        )
