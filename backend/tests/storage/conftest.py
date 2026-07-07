import pytest

from storage import init_db, close_db
from tests.factories import TEST_USER_ID


@pytest.fixture
async def db():
    conn = await init_db()
    await conn.execute(
        "TRUNCATE users, recipes, weekly_plans, shopping_items, ingredients RESTART IDENTITY CASCADE"
    )
    await conn.execute(
        "INSERT INTO users (id, email, google_sub) VALUES ($1, $2, $3)",
        TEST_USER_ID,
        "test@example.com",
        "test-google-sub",
    )
    yield conn
    await close_db(conn)
