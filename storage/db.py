import os
import asyncpg
from pathlib import Path
from yoyo import read_migrations, get_backend


def apply_migrations() -> None:
    """Synchronously apply migrations"""
    backend = get_backend(os.getenv("DATABASE_URL"))
    migrations = read_migrations(str(Path(__file__).parent.parent / "migrations"))
    with backend.lock():
        for migration in backend.to_apply(migrations):
            backend.apply_one(migration)


async def init_db() -> asyncpg.Pool:
    """Initializes the DB connection pool"""
    apply_migrations()
    return await asyncpg.create_pool(os.getenv("DATABASE_URL"), min_size=2, max_size=10)


async def close_db(db: asyncpg.Pool) -> None:
    """Closes the DB connection pool"""
    await db.close()
