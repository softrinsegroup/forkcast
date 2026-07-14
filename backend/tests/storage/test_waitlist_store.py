from models import WaitlistSignupCreate
from storage import WaitlistStore


async def test_waitlist_create_returns_id(db):
    store = WaitlistStore(db)
    id = await store.create(
        WaitlistSignupCreate(email="new@example.com", source="hero")
    )
    assert id is not None

    row = await db.fetchrow(
        "SELECT email, source FROM waitlist_signups WHERE id = $1", id
    )
    assert row["email"] == "new@example.com"
    assert row["source"] == "hero"


async def test_waitlist_duplicate_email_is_idempotent(db):
    # A repeat submit must not raise or create a second row — the landing form
    # should keep returning success without leaking that the email exists.
    store = WaitlistStore(db)
    first = await store.create(WaitlistSignupCreate(email="dup@example.com"))
    second = await store.create(WaitlistSignupCreate(email="dup@example.com"))

    assert first is not None
    assert second is None
    count = await db.fetchval("SELECT COUNT(*) FROM waitlist_signups")
    assert count == 1


async def test_waitlist_email_dedup_is_case_insensitive(db):
    # CITEXT: Foo@example.com and foo@example.com are the same person, so the
    # second must dedup rather than create a duplicate signup.
    store = WaitlistStore(db)
    await store.create(WaitlistSignupCreate(email="Foo@Example.com"))
    dup = await store.create(WaitlistSignupCreate(email="foo@example.com"))

    assert dup is None
    count = await db.fetchval("SELECT COUNT(*) FROM waitlist_signups")
    assert count == 1
