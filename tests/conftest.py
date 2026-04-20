import pytest
import storage.db as db_module
from storage import close_db


@pytest.fixture(autouse=True)
async def reset_db(tmp_path):
    """Autouse: resets the DB singleton between tests to prevent leakage."""
    yield
    await close_db()
    db_module._db = None
