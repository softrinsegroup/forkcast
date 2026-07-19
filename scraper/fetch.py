import asyncio

import httpx

USER_AGENT = "forkcast-scraper/0.1"


class PoliteFetcher:
    """
    Rate-limited HTTP fetcher for crawling a single site.

    Returns raw HTML — unlike the backend's web_fetch, which strips markup
    and would destroy the <script type="application/ld+json"> blocks we parse.
    """

    def __init__(self, concurrency: int = 2, delay: float = 1.0):
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": USER_AGENT},
        )
        self.semaphore = asyncio.Semaphore(concurrency)
        self.delay = delay

    async def fetch(self, url: str) -> str:
        """Fetch raw page text. Raises httpx.HTTPError on failure."""
        async with self.semaphore:
            response = await self.client.get(url)
            response.raise_for_status()
            # Delay inside the semaphore so each crawl slot is throttled.
            await asyncio.sleep(self.delay)
            return response.text

    async def close(self) -> None:
        await self.client.aclose()
