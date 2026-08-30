from collections.abc import AsyncGenerator

import asyncpg
from pgvector.asyncpg import register_vector

from app.config import ROOT_DIR, get_settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=settings.postgres_pool_min_size,
            max_size=settings.postgres_pool_max_size,
            init=register_vector,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def run_migrations(pool: asyncpg.Pool) -> None:
    migration_files = sorted((ROOT_DIR / "migrations").glob("*.sql"))
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext('python-ai-migrations'))"
        )
        applied = {
            row["version"]
            for row in await conn.fetch("SELECT version FROM schema_migrations")
        }
        for migration_file in migration_files:
            if migration_file.name in applied:
                continue
            await conn.execute(migration_file.read_text(encoding="utf-8"))
            await conn.execute(
                "INSERT INTO schema_migrations (version) VALUES ($1)",
                migration_file.name,
            )


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn
