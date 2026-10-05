"""Payment gateway emulation with injectable randomness and delay."""

from __future__ import annotations

import random
from collections.abc import Awaitable, Callable
from typing import Protocol

from app.config import Settings
from app.domain.exceptions import PaymentGatewayError


class PaymentLike(Protocol):
    """Minimal payment shape required by the gateway."""

    id: object


SleepFn = Callable[[float], Awaitable[None]]
RandomFloatFn = Callable[[], float]
UniformFn = Callable[[float, float], float]


class PaymentGateway:
    """Emulates an external payment gateway."""

    def __init__(
        self,
        settings: Settings,
        *,
        sleep: SleepFn | None = None,
        random_float: RandomFloatFn | None = None,
        uniform: UniformFn | None = None,
    ) -> None:
        self._settings = settings
        self._sleep = sleep
        self._random_float = random_float or random.random
        self._uniform = uniform or random.uniform

    async def process(self, payment: PaymentLike) -> None:
        """Simulate gateway processing; raises PaymentGatewayError on failure."""
        delay = self._uniform(
            self._settings.gateway_min_delay_seconds,
            self._settings.gateway_max_delay_seconds,
        )
        if self._sleep is not None:
            await self._sleep(delay)
        else:
            import asyncio

            await asyncio.sleep(delay)

        if self._random_float() >= self._settings.gateway_success_rate:
            raise PaymentGatewayError(f"Gateway declined payment {payment.id}")
