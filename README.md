# Payment Service

Asynchronous payment processing microservice for a test assignment: accept payment requests, persist them reliably, publish events to RabbitMQ via the **Outbox Pattern**, process payments with a consumer (gateway emulation + webhook), and handle **retry**, **DLQ**, and **idempotency**.

## Requirements

- **Python** 3.12 or 3.13
- **Poetry** 2.x
- **Docker** 24+
- **Docker Compose** v2

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Key variables:

| Variable | Description |
|----------|-------------|
| `API_KEY` | Static key for all API endpoints (`X-API-Key`) |
| `DATABASE_URL` | Async SQLAlchemy URL (`postgresql+asyncpg://...`) |
| `RABBITMQ_URL` | AMQP connection string |
| `OUTBOX_WORKER_ENABLED` | `true` in API container, `false` in consumer |
| `MESSAGE_MAX_ATTEMPTS` | Max consumer processing attempts (default `3`) |
| `RETRY_*` | Exponential backoff + jitter for retries |
| `GATEWAY_*` | Gateway emulation delay and success rate |

See [`.env.example`](.env.example) for the full list.

## Installation (local)

```bash
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run the consumer separately (requires PostgreSQL + RabbitMQ):

```bash
poetry run python -m app.workers.run_consumer
```

## Docker

Start the full stack (PostgreSQL, RabbitMQ, API with outbox worker, consumer):

```bash
docker compose up --build
```

Services:

| Service | Port | Health |
|---------|------|--------|
| API | `8000` | `GET /health` |
| PostgreSQL | `5432` | `pg_isready` |
| RabbitMQ | `5672`, management `15672` | `rabbitmq-diagnostics ping` |
| Consumer | — | process check |

Migrations run automatically via [`docker/entrypoint.sh`](docker/entrypoint.sh) before the app starts.

## Database

Apply migrations manually:

```bash
poetry run alembic upgrade head
```

Initial migration creates `payments`, `outbox`, and `processed_messages`.

## Tests

```bash
poetry run pytest
poetry run pytest --cov=app --cov-report=term-missing
poetry run ruff check .
poetry run ruff format --check .
```

## API

Base prefix: `/api/v1` (configurable via `API_PREFIX`).

| Method | Path | Headers | Response |
|--------|------|---------|----------|
| `POST` | `/api/v1/payments` | `X-API-Key`, `Idempotency-Key` | `202 Accepted` |
| `GET` | `/api/v1/payments/{payment_id}` | `X-API-Key` | `200 OK` |

### Example: create payment

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me-api-key" \
  -H "Idempotency-Key: order-12345-v1" \
  -d '{
    "amount": "100.00",
    "currency": "USD",
    "description": "Order #12345",
    "metadata": {"order_id": "12345"},
    "webhook_url": "https://merchant.example.com/webhooks/payments"
  }'
```

### Example: get payment

```bash
curl http://localhost:8000/api/v1/payments/{payment_id} \
  -H "X-API-Key: change-me-api-key"
```

## Swagger / OpenAPI

When the API is running:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- OpenAPI JSON: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

## RabbitMQ

| Item | Name |
|------|------|
| Exchange | `payments` (topic, durable) |
| Main queue | `payments.new` |
| Retry queue | `payments.retry` (message TTL → dead-letter back to `payments.new`) |
| DLQ | `payments.dlq` |
| Routing keys | `payments.new`, `payments.retry`, `payments.dlq` |

**Consumer flow**

1. Receive message from `payments.new`
2. Route by `event_type` (`payments.new` → payment processor)
3. Emulate gateway (2–5 s, 90% success — injectable in tests)
4. Update payment status in DB
5. Send webhook to `webhook_url`
6. On failure: republish to retry queue with backoff; after 3 attempts → DLQ
7. Unknown `event_type` → DLQ immediately

Retry delays use `compute_retry_delay()` (exponential backoff + jitter from settings).

## Outbox

Payments are created in one transaction with an outbox row:

```text
BEGIN
  INSERT payment
  INSERT outbox (status=pending)
COMMIT
```

The outbox worker publishes pending rows to RabbitMQ and marks them `published`. Failed publishes are rescheduled with backoff; after `OUTBOX_MAX_ATTEMPTS` the row becomes `failed`.

This avoids losing events when the DB commits but RabbitMQ is temporarily unavailable.

## Idempotency

**API:** `Idempotency-Key` is unique per payment payload. Same key + same body returns the existing payment; same key + different body → `409 Conflict`.

**Consumer:** `processed_messages.message_id` stores the stable outbox/event id (`event_id` in the payload). `INSERT ... ON CONFLICT DO NOTHING` prevents duplicate processing under at-least-once delivery.

```text
at-least-once delivery + idempotent consumer = protection from duplicates
```

## Retry

- **Consumer processing:** up to `MESSAGE_MAX_ATTEMPTS` (default 3), then DLQ + payment marked `failed`
- **Outbox publishing:** up to `OUTBOX_MAX_ATTEMPTS` with backoff
- **Formula:** `min(base * 2^(attempt-1), max_delay) + jitter`

Retry queue TTL survives consumer restarts (unlike in-memory-only retry counters).

## Project layout

```text
app/
  api/routers/     HTTP endpoints
  services/        Use-cases (payments, processor, gateway, webhook)
  repositories/    SQLAlchemy data access
  db/              Engine, session, Unit of Work
  messaging/       RabbitMQ, outbox worker, retry
  workers/         Consumer entrypoint
  models/          ORM entities
  schemas/         Pydantic DTOs
alembic/           Migrations
tests/             Unit and API tests
```
