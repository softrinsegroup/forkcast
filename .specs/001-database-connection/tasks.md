# Tasks: Database Connection

## Implementation

- [x] Create `storage/db.py` with `_db` singleton, `init_db()`, `get_db()`, and `close_db()`
- [x] Export `init_db`, `get_db`, `close_db` from `storage/__init__.py`
- [x] Wire `init_db` into `bot/main.py` `post_init` hook
- [x] Wire `close_db` into `bot/main.py` `post_shutdown` hook

## Testing

- [x] Write a test that calls `init_db()` and asserts `get_db()` returns a connection
- [x] Write a test that asserts `get_db()` raises `RuntimeError` before `init_db()` is called
- [x] Write a test that calls `close_db()` and asserts the connection is cleaned up
- [x] Write a test that asserts `init_db()` creates parent directories if they don't exist

## Verification

- [x] Run `uv run pytest` and confirm all tests pass
- [ ] Run the bot locally and confirm the DB file is created at `DATABASE_PATH`
