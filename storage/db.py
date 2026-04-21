import aiosqlite
from pathlib import Path
from yoyo import read_migrations, get_backend

_db: aiosqlite.Connection | None = None


# Synchronously apply migrations
def apply_migrations(db_path: str) -> None:
    backend = get_backend(f"sqlite:///{db_path}")
    migrations = read_migrations(str(Path(__file__).parent.parent / "migrations"))
    with backend.lock():
        for migration in backend.to_apply(migrations):
            backend.apply_one(migration)


async def init_db(path: str) -> None:
    global _db

    if _db is not None:
        return

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    apply_migrations(path)

    _db = await aiosqlite.connect(path)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys = ON")


def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    return _db


async def close_db() -> None:
    global _db

    if _db is not None:
        await _db.close()
        _db = None
