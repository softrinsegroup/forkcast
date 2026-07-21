"""
FastAPI app: dashboard + job API + the crawl worker in one process.
"""

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from dotenv import load_dotenv
from fastapi import FastAPI, Request

from api import router
from store import ScrapeStore, init_pool
from worker import run_worker

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.getenv("INGEST_API_KEY"):
        # Fail loud at boot: without the key every ingest would 401 mid-crawl.
        raise RuntimeError("INGEST_API_KEY is not set")

    db_pool = await init_pool()
    store = ScrapeStore(db_pool)
    await store.bootstrap()
    requeued = await store.requeue_stuck_fetching()
    if requeued:
        print(f"requeued {requeued} pages stuck in 'fetching' from a previous run")
    app.state.store = store

    worker_task = asyncio.create_task(run_worker(store))
    yield
    worker_task.cancel()
    # Await the cancellation before closing the pool, or a mid-query worker
    # races the teardown and logs spurious connection errors on every deploy.
    with suppress(asyncio.CancelledError):
        await worker_task
    await db_pool.close()


app = FastAPI(lifespan=lifespan)
app.include_router(router)


@app.get("/healthcheck")
async def healthcheck(request: Request):
    # Unauthenticated (hosting platforms probe it); pings the pool so a lost
    # DB connection turns the service unhealthy.
    await request.app.state.store.db_pool.fetchval("SELECT 1")
    return {"status": "ok"}
