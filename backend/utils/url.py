import os
import re
from bs4 import BeautifulSoup
import httpx

URL_PATTERN = re.compile(r"https?://\S+")


def extract_url(text: str) -> str | None:
    match = URL_PATTERN.search(text)

    # No URL found in text
    if not match:
        return None

    url = match.group()
    return url


async def web_fetch(url: str) -> str:
    """Using BeautifulSoup as a primary web fetch."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        return soup.get_text(separator="\n", strip=True)


async def backup_web_fetch(url: str) -> str:
    """Using jina.ai as a backup web fetch provider."""
    headers = {}
    if api_key := os.getenv("JINA_API_KEY"):
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(f"https://r.jina.ai/{url}", headers=headers)
        return resp.text
