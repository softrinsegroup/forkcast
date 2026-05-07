import pytest
import aiosqlite
import storage.db as db_module
from storage import init_db, get_db, close_db


async def test_init_db_creates_file(tmp_path):
    path = tmp_path / "test.db"
    await init_db(str(path))
    assert path.exists()


async def test_get_db_returns_connection(tmp_path):
    await init_db(str(tmp_path / "test.db"))
    conn = get_db()
    assert isinstance(conn, aiosqlite.Connection)


async def test_get_db_returns_same_object(tmp_path):
    await init_db(str(tmp_path / "test.db"))
    assert get_db() is get_db()


async def test_close_db(tmp_path):
    await init_db(str(tmp_path / "test.db"))
    await close_db()
    assert db_module._db is None


async def test_init_db_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "deep" / "test.db"
    await init_db(str(path))
    assert path.exists()


async def test_get_db_before_init_raises():
    with pytest.raises(RuntimeError):
        get_db()


async def test_close_db_before_init_is_noop():
    await close_db()  # should not raise


async def test_init_db_twice_does_not_reopen(tmp_path):
    await init_db(str(tmp_path / "test.db"))
    conn1 = get_db()
    await init_db(str(tmp_path / "test.db"))
    conn2 = get_db()
    assert conn1 is conn2
