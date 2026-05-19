import asyncpg
import pytest

from storage import init_db, close_db


async def test_init_db_returns_connection():
    conn = await init_db()
    assert isinstance(conn, asyncpg.Connection)
    await close_db(conn)


async def test_close_db():
    conn = await init_db()
    await close_db(conn)
    with pytest.raises(asyncpg.InterfaceError):
        await conn.execute("SELECT 1")


async def test_migrations_create_tables():
    conn = await init_db()
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    )
    tables = {row["table_name"] for row in rows}
    assert {"recipes", "ingredients", "weekly_plans", "shopping_items"}.issubset(tables)
    await close_db(conn)


async def test_migrations_idempotent():
    from storage.db import apply_migrations

    apply_migrations()
    apply_migrations()  # second call should not raise
