"""
The crawl loop: claims jobs and pages from Postgres and processes them.

Single process, one job at a time (FIFO) — politeness stays trivial and
matches the old CLI's behavior. All frontier state lives in the DB, so a
restart resumes wherever the last run stopped.
"""

import asyncio
import os

import httpx
from bs4 import BeautifulSoup

from client import BackendClient
from discover import extract_links, load_robots, sitemap_page_urls
from extract import extract_recipe
from fetch import USER_AGENT, PoliteFetcher
from models import Job
from store import ScrapeStore

_IDLE_POLL_SECONDS = 3
_ERROR_BACKOFF_SECONDS = 10

_INSTRUCTION_WORDS = ("instruction", "direction", "method")

# Statuses that count toward max_pages: everything terminal except skipped.
_PROCESSED_STATUSES = (
    "found",
    "ingested",
    "duplicate",
    "no_recipe",
    "robots_blocked",
    "failed",
)


def _looks_like_recipe(text: str) -> bool:
    """Cheap deterministic pre-filter so we only spend LLM calls on likely hits."""
    lowered = text.lower()
    return "ingredient" in lowered and any(w in lowered for w in _INSTRUCTION_WORDS)


async def run_worker(store: ScrapeStore) -> None:
    """
    Poll for jobs forever; runs as a background task in the app lifespan.

    Nothing awaits this task, so an exception escaping the loop would kill the
    worker invisibly and leave jobs sitting in 'pending' with no signal. Every
    cycle is guarded — the frontier is durable, so backing off and retrying
    resumes exactly where the failure hit.
    """
    while True:
        try:
            await _poll_once(store)
        except Exception as e:
            print(f"[worker] cycle failed, retrying in {_ERROR_BACKOFF_SECONDS}s: {e}")
            await asyncio.sleep(_ERROR_BACKOFF_SECONDS)


async def _poll_once(store: ScrapeStore) -> None:
    """One cycle: claim and run a job, or idle when the queue is empty."""
    job = await store.claim_next_job()
    if job is None:
        await asyncio.sleep(_IDLE_POLL_SECONDS)
        return
    print(f"[job {job.id}] claimed: {job.root_url}")
    try:
        await _run_job(store, job)
    except Exception as e:
        # A bad job is marked failed and skipped; a DB outage propagates to
        # run_worker, which backs off and retries the same job.
        print(f"[job {job.id}] crashed: {e}")
        await store.finish_job(job.id, "failed", error=str(e))


async def _run_job(store: ScrapeStore, job: Job) -> None:
    fetcher = PoliteFetcher(job.concurrency, job.delay_seconds)
    client = BackendClient(
        os.getenv("FORKCAST_API_URL", "http://localhost:8000"),
        os.getenv("INGEST_API_KEY", ""),
    )
    try:
        robots, sitemap_directives = await load_robots(fetcher, job.root_url)

        bfs = job.bfs
        if job.seeded_at is None:
            urls = await sitemap_page_urls(
                fetcher, job.root_url, sitemap_directives, job.max_pages
            )
            bfs = not urls
            await store.enqueue_urls(job.id, urls or [job.root_url])
            await store.mark_seeded(job.id, bfs=bfs)
            print(
                f"[job {job.id}] seeded "
                + (f"{len(urls)} sitemap URLs" if urls else "root URL (BFS crawl)")
            )

        workers = [
            asyncio.create_task(_page_loop(store, job, bfs, robots, fetcher, client))
            for _ in range(job.concurrency)
        ]
        try:
            await asyncio.gather(*workers)
        except Exception:
            for worker in workers:
                worker.cancel()
            raise
    finally:
        await fetcher.close()
        await client.close()

    if await store.get_job_status(job.id) == "cancelled":
        await store.finish_job(job.id, "cancelled")
        print(f"[job {job.id}] cancelled")
        return

    counts = await store.job_counts(job.id)
    fetched = sum(
        counts.get(s, 0) for s in ("found", "ingested", "duplicate", "no_recipe")
    )
    if fetched > 0:
        await store.finish_job(job.id, "done")
    else:
        await store.finish_job(job.id, "failed", error="no pages fetched")
    print(f"[job {job.id}] finished: {counts}")


async def _page_loop(
    store: ScrapeStore,
    job: Job,
    bfs: bool,
    robots,
    fetcher: PoliteFetcher,
    client: BackendClient,
) -> None:
    """One crawl slot: claim queued pages until the job has nothing left."""
    while True:
        if await store.get_job_status(job.id) == "cancelled":
            return
        counts = await store.job_counts(job.id)
        processed = sum(counts.get(s, 0) for s in _PROCESSED_STATUSES)
        if processed >= job.max_pages:
            return
        page = await store.claim_next_page(job.id)
        if page is None:
            # A sibling slot mid-fetch may still enqueue BFS links.
            if counts.get("fetching", 0) > 0:
                await asyncio.sleep(1)
                continue
            return
        await _process_page(store, job, bfs, robots, fetcher, client, page)


async def _process_page(
    store: ScrapeStore,
    job: Job,
    bfs: bool,
    robots,
    fetcher: PoliteFetcher,
    client: BackendClient,
    page,
) -> None:
    page_id, url = page["id"], page["url"]

    if not robots.can_fetch(USER_AGENT, url):
        await store.finish_page(page_id, "robots_blocked")
        return

    try:
        html = await fetcher.fetch(url)
    except httpx.HTTPError as e:
        await store.finish_page(page_id, "failed", error=f"fetch: {e}")
        return
    print(f"[job {job.id}] fetched {url}")

    if bfs and await store.count_pages(job.id) < job.max_pages * 2:
        await store.enqueue_urls(job.id, list(extract_links(html, url, job.root_url)))

    recipe = extract_recipe(html, url)
    payload = recipe.model_dump(mode="json") if recipe is not None else None

    if payload is None and job.llm_fallback:
        page_text = BeautifulSoup(html, "html.parser").get_text()
        # Pre-filter before consuming cap; the cap is spent per attempt, not
        # per hit — same semantics as the old CLI's LlmFallback.
        if _looks_like_recipe(page_text) and await store.try_use_llm(job.id):
            try:
                payload = await client.parse(url, page_text)
            except httpx.HTTPError as e:
                await store.finish_page(page_id, "failed", error=f"llm parse: {e}")
                return

    if payload is None:
        await store.finish_page(page_id, "no_recipe")
        return

    if job.dry_run:
        await store.finish_page(page_id, "found", recipe_name=payload["name"])
        print(f"[job {job.id}]   recipe (dry run): {payload['name']}")
        return

    try:
        result = await client.ingest(payload)
    except httpx.HTTPError as e:
        await store.finish_page(page_id, "failed", error=f"ingest: {e}")
        return
    status = "ingested" if result["created"] else "duplicate"
    await store.finish_page(
        page_id, status, recipe_name=payload["name"], recipe_id=result["id"]
    )
    print(f"[job {job.id}]   {status}: {payload['name']}")
