"""
Scraper-owned models.

Recipe/Ingredient are this service's binding of the backend's ingest wire
contract (POST /recipes/ingest) — deliberately not imported or shared. The
backend validates every payload, so drift fails loud as a 422 on ingest.
"""

from datetime import datetime

from pydantic import BaseModel, field_validator


class Ingredient(BaseModel):
    id: int
    name: str
    unit: str
    amount: float


class Recipe(BaseModel):
    name: str
    instructions: list[str]
    ingredients: list[Ingredient]
    servings: int
    prep_minutes: int
    cook_minutes: int
    tags: list[str]
    source_url: str


class JobCreate(BaseModel):
    root_url: str
    max_pages: int = 500
    concurrency: int = 2
    delay_seconds: float = 1.0
    llm_fallback: bool = False
    llm_cap: int = 20
    dry_run: bool = False

    @field_validator("root_url")
    @classmethod
    def _ensure_scheme(cls, value: str) -> str:
        return value if value.startswith("http") else f"https://{value}"


class Job(BaseModel):
    id: int
    root_url: str
    status: str
    max_pages: int
    concurrency: int
    delay_seconds: float
    llm_fallback: bool
    llm_cap: int
    llm_used: int
    dry_run: bool
    bfs: bool
    seeded_at: datetime | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    counts: dict[str, int] = {}


class PageRow(BaseModel):
    url: str
    status: str
    recipe_name: str | None
    recipe_id: int | None
    error: str | None
    updated_at: datetime
