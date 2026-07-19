import xml.etree.ElementTree as ET
from collections import deque
from typing import Iterator
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from fetch import PoliteFetcher

# Obvious non-HTML links to skip during BFS crawling.
_SKIP_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".pdf",
    ".zip",
    ".mp4",
    ".mp3",
    ".css",
    ".js",
    ".xml",
    ".rss",
)


def _host(url: str) -> str:
    """Hostname normalized for same-site comparison (www. is insignificant)."""
    netloc = urlparse(url).netloc.lower()
    return netloc.removeprefix("www.")


def same_host(url: str, root: str) -> bool:
    return _host(url) == _host(root)


async def load_robots(
    fetcher: PoliteFetcher, root: str
) -> tuple[RobotFileParser, list[str]]:
    """
    Fetch robots.txt; returns the parser and any Sitemap: directives.

    A missing or unfetchable robots.txt means everything is allowed.
    """
    robots = RobotFileParser()
    try:
        text = await fetcher.fetch(urljoin(root, "/robots.txt"))
        robots.parse(text.splitlines())
    except httpx.HTTPError:
        robots.parse([])
    return robots, list(robots.site_maps() or [])


async def sitemap_page_urls(
    fetcher: PoliteFetcher,
    root: str,
    sitemap_urls: list[str],
    max_pages: int,
) -> list[str]:
    """
    Collect same-host page URLs from sitemaps, recursing into indexes.

    Tries robots.txt Sitemap: directives first, then the conventional paths.
    Returns [] if the site has no parseable sitemap (caller falls back to BFS).
    """
    candidates = sitemap_urls or [
        urljoin(root, "/sitemap.xml"),
        urljoin(root, "/sitemap_index.xml"),
    ]

    pages: list[str] = []
    seen: set[str] = set()
    queue = deque(candidates)
    while queue and len(pages) < max_pages:
        sitemap_url = queue.popleft()
        if sitemap_url in seen:
            continue
        seen.add(sitemap_url)

        try:
            xml_text = await fetcher.fetch(sitemap_url)
            doc = ET.fromstring(xml_text)
        except (httpx.HTTPError, ET.ParseError):
            continue

        # <sitemapindex> nests child sitemaps; <urlset> holds page URLs.
        for loc in doc.findall("{*}sitemap/{*}loc"):
            if loc.text:
                queue.append(loc.text.strip())
        for loc in doc.findall("{*}url/{*}loc"):
            if loc.text and same_host(loc.text.strip(), root):
                pages.append(loc.text.strip())

    return pages[:max_pages]


def extract_links(html: str, base_url: str, root: str) -> Iterator[str]:
    """Same-host page links from a fetched page, for BFS fallback crawling."""
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        url, _ = urldefrag(urljoin(base_url, anchor["href"]))
        if not url.startswith("http"):
            continue
        if not same_host(url, root):
            continue
        if urlparse(url).path.lower().endswith(_SKIP_EXTENSIONS):
            continue
        yield url
