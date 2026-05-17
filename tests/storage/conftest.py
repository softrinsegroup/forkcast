import pytest

from storage import init_db, close_db


@pytest.fixture
async def db(tmp_path):
    conn = await init_db(str(tmp_path / "test.db"))
    yield conn
    await close_db(conn)
