import pytest

from storage import init_db, close_db


@pytest.fixture
async def db():
    conn = await init_db()
    await conn.execute(
        "TRUNCATE recipes, weekly_plans, shopping_items, ingredients RESTART IDENTITY CASCADE"
    )
    yield conn
    await close_db(conn)
