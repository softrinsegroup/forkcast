"""
Postgres persistence for crawl jobs and the per-URL page frontier.

Lives in a scraper-owned schema inside the same Postgres instance as the
backend. Bootstrap DDL is idempotent and runs at startup — deliberately not
yoyo: the backend's migrations already own the default `_yoyo_migration`
bookkeeping table in this database.
"""

import json
import os

import asyncpg

from models import Job, JobCreate, PageRow

_DDL = """
CREATE SCHEMA IF NOT EXISTS scraper;

CREATE TABLE IF NOT EXISTS scraper.jobs (
    id            BIGSERIAL PRIMARY KEY,
    root_url      TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','running','done','failed','cancelled')),
    max_pages     INT NOT NULL DEFAULT 500,
    concurrency   INT NOT NULL DEFAULT 2,
    delay_seconds REAL NOT NULL DEFAULT 1.0,
    llm_fallback  BOOLEAN NOT NULL DEFAULT FALSE,
    llm_cap       INT NOT NULL DEFAULT 20,
    llm_used      INT NOT NULL DEFAULT 0,
    dry_run       BOOLEAN NOT NULL DEFAULT FALSE,
    bfs           BOOLEAN NOT NULL DEFAULT FALSE,
    seeded_at     TIMESTAMPTZ,
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS scraper.pages (
    id          BIGSERIAL PRIMARY KEY,
    job_id      BIGINT NOT NULL REFERENCES scraper.jobs(id) ON DELETE CASCADE,
    url         TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued','fetching','found','ingested','duplicate',
                                  'no_recipe','robots_blocked','failed','skipped')),
    recipe_name TEXT,
    recipe_id   BIGINT,
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (job_id, url)
);

CREATE INDEX IF NOT EXISTS pages_claim_idx ON scraper.pages (job_id, id)
    WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS pages_status_idx ON scraper.pages (job_id, status);
"""


async def init_pool() -> asyncpg.Pool:
    """Initializes the DB connection pool"""
    return await asyncpg.create_pool(os.getenv("DATABASE_URL"), min_size=1, max_size=5)


def _job_from_row(row: asyncpg.Record, counts: dict[str, int]) -> Job:
    return Job(**{**dict(row), "counts": counts})


class ScrapeStore:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def bootstrap(self) -> None:
        """Idempotently create the scraper schema, tables, and indexes."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(_DDL)

    # -- jobs ---------------------------------------------------------------

    async def create_job(self, data: JobCreate) -> Job:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO scraper.jobs (root_url, max_pages, concurrency, "
                "delay_seconds, llm_fallback, llm_cap, dry_run) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *",
                data.root_url,
                data.max_pages,
                data.concurrency,
                data.delay_seconds,
                data.llm_fallback,
                data.llm_cap,
                data.dry_run,
            )
            return _job_from_row(row, {})

    async def get_job(self, job_id: int) -> Job | None:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM scraper.jobs WHERE id = $1", job_id
            )
            if row is None:
                return None
            return _job_from_row(row, await self._counts(conn, job_id))

    async def list_jobs(self, limit: int = 50) -> list[Job]:
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT j.*, "
                "  (SELECT jsonb_object_agg(s.status, s.n) "
                "   FROM (SELECT status, count(*) AS n FROM scraper.pages p "
                "         WHERE p.job_id = j.id GROUP BY status) s) AS counts "
                "FROM scraper.jobs j ORDER BY j.id DESC LIMIT $1",
                limit,
            )
            jobs = []
            for row in rows:
                data = dict(row)
                counts = json.loads(data.pop("counts") or "{}")
                jobs.append(Job(**{**data, "counts": counts}))
            return jobs

    async def job_counts(self, job_id: int) -> dict[str, int]:
        async with self.db_pool.acquire() as conn:
            return await self._counts(conn, job_id)

    async def _counts(self, conn: asyncpg.Connection, job_id: int) -> dict[str, int]:
        rows = await conn.fetch(
            "SELECT status, count(*) AS n FROM scraper.pages "
            "WHERE job_id = $1 GROUP BY status",
            job_id,
        )
        return {row["status"]: row["n"] for row in rows}

    async def get_job_status(self, job_id: int) -> str | None:
        async with self.db_pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT status FROM scraper.jobs WHERE id = $1", job_id
            )

    async def claim_next_job(self) -> Job | None:
        """
        Claim the oldest pending/running job, FIFO — one job at a time.

        Re-claims `running` jobs so a crawl interrupted by a restart resumes.
        SKIP LOCKED only serializes the claim statement itself; the row lock
        ends when it commits, so this does NOT stop a second replica from
        claiming a job already in flight. Single-replica only — running two
        would need a lease column (owner + expiry) refreshed during the crawl.
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE scraper.jobs "
                "SET status = 'running', started_at = COALESCE(started_at, now()) "
                "WHERE id = (SELECT id FROM scraper.jobs "
                "            WHERE status IN ('pending', 'running') "
                "            ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED) "
                "RETURNING *"
            )
            if row is None:
                return None
            return _job_from_row(row, await self._counts(conn, row["id"]))

    async def mark_seeded(self, job_id: int, bfs: bool) -> None:
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE scraper.jobs SET seeded_at = now(), bfs = $2 WHERE id = $1",
                job_id,
                bfs,
            )

    async def finish_job(
        self, job_id: int, status: str, error: str | None = None
    ) -> None:
        """Terminal transition: leftover queued pages are marked skipped."""
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE scraper.pages SET status = 'skipped', updated_at = now() "
                    "WHERE job_id = $1 AND status = 'queued'",
                    job_id,
                )
                await conn.execute(
                    "UPDATE scraper.jobs "
                    "SET status = $2, error = $3, finished_at = now() "
                    "WHERE id = $1",
                    job_id,
                    status,
                    error,
                )

    async def cancel_job(self, job_id: int) -> Job | None:
        """
        Cancel a pending/running job; None if it doesn't exist or is terminal.

        The worker notices mid-crawl and finalizes; for a job it never claimed
        the finished_at set here is the whole finalization.
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE scraper.jobs SET status = 'cancelled', finished_at = now() "
                "WHERE id = $1 AND status IN ('pending', 'running') RETURNING *",
                job_id,
            )
            if row is None:
                return None
            return _job_from_row(row, await self._counts(conn, job_id))

    async def retry_failed(self, job_id: int) -> int:
        """
        Requeue failed/skipped pages; reopen a terminal job as pending so the
        worker re-claims it. Returns the number of pages requeued.
        """
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                result = await conn.execute(
                    "UPDATE scraper.pages "
                    "SET status = 'queued', error = NULL, updated_at = now() "
                    "WHERE job_id = $1 AND status IN ('failed', 'skipped')",
                    job_id,
                )
                await conn.execute(
                    "UPDATE scraper.jobs "
                    "SET status = 'pending', error = NULL, finished_at = NULL "
                    "WHERE id = $1 AND status IN ('done', 'failed', 'cancelled')",
                    job_id,
                )
                return int(result.split()[-1])

    async def try_use_llm(self, job_id: int) -> bool:
        """Atomically consume one LLM call; False when the job's cap is spent."""
        async with self.db_pool.acquire() as conn:
            used = await conn.fetchval(
                "UPDATE scraper.jobs SET llm_used = llm_used + 1 "
                "WHERE id = $1 AND llm_used < llm_cap RETURNING llm_used",
                job_id,
            )
            return used is not None

    # -- pages --------------------------------------------------------------

    async def enqueue_urls(self, job_id: int, urls: list[str]) -> int:
        """
        Add URLs to the frontier. The (job_id, url) unique constraint is the
        persistent "seen" set: duplicates are dropped. Returns rows inserted.
        """
        if not urls:
            return 0
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                "INSERT INTO scraper.pages (job_id, url) "
                "SELECT $1, unnest($2::text[]) "
                "ON CONFLICT (job_id, url) DO NOTHING",
                job_id,
                urls,
            )
            return int(result.split()[-1])

    async def claim_next_page(self, job_id: int) -> asyncpg.Record | None:
        """Claim the oldest queued page (id, url); None when the frontier is empty."""
        async with self.db_pool.acquire() as conn:
            return await conn.fetchrow(
                "UPDATE scraper.pages SET status = 'fetching', updated_at = now() "
                "WHERE id = (SELECT id FROM scraper.pages "
                "            WHERE job_id = $1 AND status = 'queued' "
                "            ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED) "
                "RETURNING id, url",
                job_id,
            )

    async def finish_page(
        self,
        page_id: int,
        status: str,
        recipe_name: str | None = None,
        recipe_id: int | None = None,
        error: str | None = None,
    ) -> None:
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE scraper.pages "
                "SET status = $2, recipe_name = $3, recipe_id = $4, error = $5, "
                "    updated_at = now() "
                "WHERE id = $1",
                page_id,
                status,
                recipe_name,
                recipe_id,
                error,
            )

    async def requeue_stuck_fetching(self) -> int:
        """
        Startup recovery: pages orphaned mid-fetch by a crash/restart return
        to the frontier. Returns the number of pages requeued.
        """
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE scraper.pages SET status = 'queued', updated_at = now() "
                "WHERE status = 'fetching'"
            )
            return int(result.split()[-1])

    async def count_pages(self, job_id: int) -> int:
        """Total frontier size for a job (any status) — the BFS growth guard."""
        async with self.db_pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT count(*) FROM scraper.pages WHERE job_id = $1", job_id
            )

    async def list_pages(
        self, job_id: int, status: str | None = None, limit: int = 100
    ) -> list[PageRow]:
        query = (
            "SELECT url, status, recipe_name, recipe_id, error, updated_at "
            "FROM scraper.pages WHERE job_id = $1"
        )
        args: list = [job_id]
        if status is not None:
            query += " AND status = $2"
            args.append(status)
        query += f" ORDER BY updated_at DESC LIMIT ${len(args) + 1}"
        args.append(limit)
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [PageRow(**dict(row)) for row in rows]
