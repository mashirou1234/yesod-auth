"""Bounded readiness check for disposable CI services before migrations."""

import asyncio

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def wait_services() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    cache = Redis.from_url(settings.VALKEY_URL)
    try:
        for _ in range(30):
            try:
                async with asyncio.timeout(2):
                    async with engine.connect() as connection:
                        await connection.execute(text("SELECT 1"))
                    await cache.ping()
                return
            except Exception:
                # Connection errors can contain credentials; never echo their messages.
                await asyncio.sleep(1)
        raise SystemExit("PostgreSQL/Valkey readiness timed out")
    finally:
        await cache.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(wait_services())
