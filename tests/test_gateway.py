"""Payment gateway emulation tests."""

import pytest

from app.domain.exceptions import PaymentGatewayError
from app.services.gateway import PaymentGateway


@pytest.mark.asyncio
async def test_gateway_success_is_deterministic_with_mocks(settings, sample_payment) -> None:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    gateway = PaymentGateway(
        settings,
        sleep=fake_sleep,
        random_float=lambda: 0.0,
        uniform=lambda _a, _b: 2.5,
    )
    await gateway.process(sample_payment)
    assert sleeps == [2.5]


@pytest.mark.asyncio
async def test_gateway_failure_is_deterministic_with_mocks(settings, sample_payment) -> None:
    async def fake_sleep(_delay: float) -> None:
        return None

    gateway = PaymentGateway(
        settings,
        sleep=fake_sleep,
        random_float=lambda: 0.95,
        uniform=lambda _a, _b: 3.0,
    )
    with pytest.raises(PaymentGatewayError):
        await gateway.process(sample_payment)
