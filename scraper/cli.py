"""
One-off CLI for the scraper service — queue jobs and check status without
opening the dashboard. Writes straight to the queue in Postgres; the service
worker does the crawling.

Run from scraper/:

    uv run python cli.py enqueue https://somerecipesite.com \
        [--max-pages 500] [--concurrency 2] [--delay 1.0] \
        [--llm-fallback] [--llm-cap 20] [--dry-run]
    uv run python cli.py list

Requires DATABASE_URL in the environment (or scraper/.env).
"""

import argparse
import asyncio

from dotenv import load_dotenv

from models import JobCreate
from store import ScrapeStore, init_pool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    enqueue = sub.add_parser("enqueue", help="Queue a crawl job")
    enqueue.add_argument("root", help="Root URL of the site to scrape")
    enqueue.add_argument("--max-pages", type=int, default=500)
    enqueue.add_argument("--concurrency", type=int, default=2)
    enqueue.add_argument("--delay", type=float, default=1.0)
    enqueue.add_argument(
        "--llm-fallback",
        action="store_true",
        help="LLM-parse pages without JSON-LD via the backend's /recipes/parse",
    )
    enqueue.add_argument("--llm-cap", type=int, default=20)
    enqueue.add_argument(
        "--dry-run",
        action="store_true",
        help="Record found recipes, but don't POST them to the backend",
    )

    sub.add_parser("list", help="List recent jobs")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    pool = await init_pool()
    store = ScrapeStore(pool)
    try:
        await store.bootstrap()
        if args.command == "enqueue":
            job = await store.create_job(
                JobCreate(
                    root_url=args.root,
                    max_pages=args.max_pages,
                    concurrency=args.concurrency,
                    delay_seconds=args.delay,
                    llm_fallback=args.llm_fallback,
                    llm_cap=args.llm_cap,
                    dry_run=args.dry_run,
                )
            )
            print(f"job {job.id} queued: {job.root_url}")
        else:
            for job in await store.list_jobs(limit=20):
                counts = job.counts
                print(
                    f"[{job.id}] {job.status:<9} {job.root_url}  "
                    f"queued={counts.get('queued', 0)} "
                    f"found={counts.get('found', 0)} "
                    f"ingested={counts.get('ingested', 0)} "
                    f"failed={counts.get('failed', 0)}"
                )
    finally:
        await pool.close()


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(run(parse_args()))
