"""
Recipe scraper CLI — crawls a site and ingests recipes via the backend API.

Run from backend/:

    uv run python -m scraper https://somerecipesite.com \
        [--max-pages 500] [--concurrency 2] [--delay 1.0] \
        [--llm-fallback] [--llm-cap 20] [--dry-run] \
        [--api-url http://localhost:8000]

Requires INGEST_API_KEY in the environment (or backend/.env) unless --dry-run.
"""

import argparse
import asyncio
import os
import sys
from collections import Counter, deque

import httpx
from dotenv import load_dotenv

from scraper.client import IngestClient
from scraper.discover import extract_links, load_robots, sitemap_page_urls
from scraper.extract import extract_recipe
from scraper.fetch import USER_AGENT, PoliteFetcher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="scraper", description=__doc__)
    parser.add_argument("root", help="Root URL of the site to scrape")
    parser.add_argument("--max-pages", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument(
        "--llm-fallback",
        action="store_true",
        help="Use the LLM on pages without JSON-LD (requires ANTHROPIC_API_KEY)",
    )
    parser.add_argument("--llm-cap", type=int, default=20, help="Max LLM calls per run")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and report, but don't POST to the backend",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("FORKCAST_API_URL", "http://localhost:8000"),
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> int:
    root = args.root if args.root.startswith("http") else f"https://{args.root}"

    llm = None
    if args.llm_fallback:
        # Imported lazily: pulls in langchain, only needed with the flag on.
        from scraper.llm_fallback import LlmFallback

        llm = LlmFallback(args.llm_cap)  # raises without ANTHROPIC_API_KEY

    client = None
    if not args.dry_run:
        api_key = os.getenv("INGEST_API_KEY")
        if not api_key:
            print("error: INGEST_API_KEY is not set (use --dry-run to skip ingest)")
            return 1
        client = IngestClient(args.api_url, api_key)

    fetcher = PoliteFetcher(args.concurrency, args.delay)
    stats: Counter[str] = Counter()

    async def process_html(url: str, html: str) -> None:
        recipe = extract_recipe(html, url)
        if recipe is None and llm is not None:
            recipe = await llm.try_parse(html, url)
        if recipe is None:
            stats["no_recipe"] += 1
            return

        stats["found"] += 1
        if args.dry_run:
            print(f"  recipe: {recipe.name} ({url})")
            return
        try:
            created = await client.ingest(recipe)
        except httpx.HTTPError as e:
            stats["failed"] += 1
            print(f"  ingest failed: {url}: {e}")
            return
        stats["ingested" if created else "skipped"] += 1
        print(f"  {'ingested' if created else 'skipped (duplicate)'}: {recipe.name}")

    async def process_url(url: str) -> str | None:
        """Fetch one page and run extraction/ingest. Returns HTML for BFS."""
        if not robots.can_fetch(USER_AGENT, url):
            stats["robots_blocked"] += 1
            return None
        try:
            html = await fetcher.fetch(url)
        except httpx.HTTPError as e:
            stats["failed"] += 1
            print(f"  fetch failed: {url}: {e}")
            return None
        stats["fetched"] += 1
        print(f"[{stats['fetched']}] {url}")
        await process_html(url, html)
        return html

    try:
        robots, sitemap_directives = await load_robots(fetcher, root)
        urls = await sitemap_page_urls(
            fetcher, root, sitemap_directives, args.max_pages
        )

        if urls:
            print(f"discovered {len(urls)} URLs via sitemap")
            await asyncio.gather(*(process_url(url) for url in urls))
        else:
            print("no sitemap found, falling back to BFS crawl")
            queue: deque[str] = deque([root])
            seen: set[str] = {root}
            while queue and stats["fetched"] < args.max_pages:
                url = queue.popleft()
                html = await process_url(url)
                if html is None:
                    continue
                for link in extract_links(html, url, root):
                    if link not in seen:
                        seen.add(link)
                        queue.append(link)
    finally:
        await fetcher.close()
        if client is not None:
            await client.close()

    print(
        f"\ndone: {stats['fetched']} pages fetched, "
        f"{stats['found']} recipes found, "
        f"{stats['ingested']} ingested, "
        f"{stats['skipped']} skipped (duplicate), "
        f"{stats['no_recipe']} no recipe, "
        f"{stats['robots_blocked']} blocked by robots.txt, "
        f"{stats['failed']} failed"
    )

    if stats["fetched"] == 0:
        return 1
    if stats["failed"] > 0 and stats["ingested"] == 0 and stats["skipped"] == 0:
        return 1
    return 0


def main() -> None:
    load_dotenv()
    sys.exit(asyncio.run(run(parse_args())))


if __name__ == "__main__":
    main()
