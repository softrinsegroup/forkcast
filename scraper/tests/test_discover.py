from pathlib import Path

import httpx

from discover import extract_links, load_robots, sitemap_page_urls
from fetch import USER_AGENT

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = "https://example.com"


class FakeFetcher:
    """PoliteFetcher stand-in: serves canned responses, 404s everything else."""

    def __init__(self, responses: dict[str, str]):
        self.responses = responses
        self.requested: list[str] = []

    async def fetch(self, url: str) -> str:
        self.requested.append(url)
        if url not in self.responses:
            raise httpx.HTTPError(f"404: {url}")
        return self.responses[url]


# ---------------------------------------------------------------------------
# sitemap_page_urls
# ---------------------------------------------------------------------------


async def test_sitemap_index_recursion_and_host_filter():
    # A sitemap index must be followed into child sitemaps, and URLs pointing
    # off-site must never enter the crawl (we only scrape the given domain).
    fetcher = FakeFetcher(
        {
            f"{ROOT}/sitemap.xml": (FIXTURES / "sitemap_index.xml").read_text(),
            f"{ROOT}/sitemap_recipes.xml": (
                FIXTURES / "sitemap_recipes.xml"
            ).read_text(),
        }
    )
    urls = await sitemap_page_urls(fetcher, ROOT, [], max_pages=10)
    # www.example.com counts as same-host; other-site.com is excluded
    assert urls == [
        "https://www.example.com/recipes/pancakes",
        "https://example.com/recipes/chicken",
    ]


async def test_sitemap_missing_returns_empty():
    # No sitemap anywhere → caller must get [] and fall back to BFS crawling.
    urls = await sitemap_page_urls(FakeFetcher({}), ROOT, [], max_pages=10)
    assert urls == []


async def test_sitemap_respects_max_pages():
    fetcher = FakeFetcher(
        {f"{ROOT}/sitemap.xml": (FIXTURES / "sitemap_recipes.xml").read_text()}
    )
    urls = await sitemap_page_urls(fetcher, ROOT, [], max_pages=1)
    assert len(urls) == 1


# ---------------------------------------------------------------------------
# load_robots
# ---------------------------------------------------------------------------


async def test_robots_disallow_is_enforced():
    fetcher = FakeFetcher(
        {f"{ROOT}/robots.txt": "User-agent: *\nDisallow: /private/\n"}
    )
    robots, sitemaps = await load_robots(fetcher, ROOT)
    assert not robots.can_fetch(USER_AGENT, f"{ROOT}/private/secret")
    assert robots.can_fetch(USER_AGENT, f"{ROOT}/recipes/pancakes")
    assert sitemaps == []


async def test_robots_sitemap_directive_collected():
    fetcher = FakeFetcher(
        {f"{ROOT}/robots.txt": f"Sitemap: {ROOT}/custom_sitemap.xml\n"}
    )
    _, sitemaps = await load_robots(fetcher, ROOT)
    assert sitemaps == [f"{ROOT}/custom_sitemap.xml"]


async def test_missing_robots_allows_everything():
    # A site without robots.txt must not block the crawl.
    robots, _ = await load_robots(FakeFetcher({}), ROOT)
    assert robots.can_fetch(USER_AGENT, f"{ROOT}/anything")


# ---------------------------------------------------------------------------
# extract_links
# ---------------------------------------------------------------------------


def test_extract_links_filters_and_normalizes():
    html = (FIXTURES / "non_recipe.html").read_text()
    links = set(extract_links(html, f"{ROOT}/about", ROOT))
    # Relative links resolved, fragments stripped (dedup), external hosts,
    # binary files, and mailto: all excluded.
    assert links == {
        f"{ROOT}/recipes/pancakes",
        f"{ROOT}/recipes/chicken/",
    }
