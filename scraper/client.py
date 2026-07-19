import httpx


class BackendClient:
    """
    HTTP client for the backend's machine endpoints (Bearer INGEST_API_KEY).

    POST /recipes/ingest stores a recipe; POST /recipes/parse runs the
    backend's LLM extraction on page text — the prompt and schema live only
    backend-side, so recipes from parse() are forwarded to ingest() as opaque
    dicts.
    """

    def __init__(self, api_url: str, api_key: str):
        self.client = httpx.AsyncClient(
            base_url=api_url,
            timeout=30,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def ingest(self, recipe: dict) -> dict:
        """
        POST one recipe payload. Returns {"id": int, "created": bool} —
        created=False means it was skipped as a duplicate source_url.

        Raises httpx.HTTPError on any non-200 — the caller marks the page
        failed and moves on.
        """
        response = await self.client.post("/recipes/ingest", json=recipe)
        response.raise_for_status()
        return response.json()

    async def parse(self, url: str, page_text: str) -> dict | None:
        """
        Ask the backend to LLM-parse page text. Returns the recipe payload,
        or None when the page doesn't parse as a valid recipe.

        Raises httpx.HTTPError on any non-200 (incl. 502 for LLM failures).
        Long timeout: the backend call blocks on an LLM completion.
        """
        response = await self.client.post(
            "/recipes/parse",
            json={"url": url, "page_text": page_text},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["recipe"]

    async def close(self) -> None:
        await self.client.aclose()
