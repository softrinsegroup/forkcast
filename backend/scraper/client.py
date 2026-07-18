import httpx

from models import RecipeCreate


class IngestClient:
    """HTTP client for the backend's POST /recipes/ingest endpoint."""

    def __init__(self, api_url: str, api_key: str):
        self.client = httpx.AsyncClient(
            base_url=api_url,
            timeout=30,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def ingest(self, recipe: RecipeCreate) -> bool:
        """
        POST one recipe. True if created, False if skipped as a duplicate.

        Raises httpx.HTTPError on any non-200 — the caller counts it as failed
        and moves on.
        """
        response = await self.client.post(
            "/recipes/ingest", json=recipe.model_dump(mode="json")
        )
        response.raise_for_status()
        return response.json()["created"]

    async def close(self) -> None:
        await self.client.aclose()
