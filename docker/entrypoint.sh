#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."
python - <<'PY'
import asyncio
import os
import sys

import asyncpg


async def wait_for_postgres() -> None:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    user = os.getenv("POSTGRES_USER", "payment")
    password = os.getenv("POSTGRES_PASSWORD", "payment")
    database = os.getenv("POSTGRES_DB", "payments")

    last_error: Exception | None = None
    for _ in range(60):
        try:
            conn = await asyncpg.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
            )
            await conn.close()
            print("PostgreSQL is ready")
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            await asyncio.sleep(1)

    print(f"PostgreSQL is not available: {last_error}", file=sys.stderr)
    raise SystemExit(1)


asyncio.run(wait_for_postgres())
PY

echo "Applying Alembic migrations..."
alembic upgrade head

echo "Starting application: $*"
exec "$@"
