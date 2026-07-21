import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from agent.workflows.parse_recipe import parse_page_text
from api.deps import get_current_user, require_ingest_key
from storage import RecipeStore
from models import Recipe, RecipeCreate

router = APIRouter(prefix="/recipes", tags=["recipes"])


class ParsePageRequest(BaseModel):
    url: str
    page_text: str


@router.post("/ingest", dependencies=[Depends(require_ingest_key)])
async def ingest(recipe: RecipeCreate, request: Request):
    """
    Machine ingest endpoint for the scraper service.
    Idempotent on source_url: a recipe already ingested from the same URL is
    skipped, not duplicated. Always 200 so the scraper can count skips without
    error handling. Embedding happens via the reconcile loop (embedded=false).
    """
    recipe_store: RecipeStore = request.app.state.recipe_store

    existing_id = await recipe_store.get_id_by_source_url(recipe.source_url)
    if existing_id is not None:
        return {"id": existing_id, "created": False}

    try:
        recipe_id = await recipe_store.create(recipe)
    except asyncpg.UniqueViolationError:
        # Lost a race past the lookup above. The unique index on source_url is
        # the real dedup guarantee; this is just the read-back.
        existing_id = await recipe_store.get_id_by_source_url(recipe.source_url)
        if existing_id is None:
            raise
        return {"id": existing_id, "created": False}

    return {"id": recipe_id, "created": True}


@router.post("/parse", dependencies=[Depends(require_ingest_key)])
async def parse(body: ParsePageRequest, request: Request):
    """
    Machine parse endpoint for the scraper service's LLM fallback.
    Runs the same LLM extraction as the chat parse flow (live PromptStore
    prompt), but on page text the scraper already fetched — no re-fetch.
    Returns {"recipe": null} when the page doesn't parse as a valid recipe;
    502 when the LLM call itself fails so the scraper records a failed page.
    """
    try:
        recipe = await parse_page_text(
            request.app.state.model_agent,
            request.app.state.prompt_store,
            body.url,
            body.page_text,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM parse failed: {e}")

    if recipe is None:
        return {"recipe": None}
    return {"recipe": recipe.model_dump(mode="json")}


@router.get("/{id}", dependencies=[Depends(get_current_user)])
async def get(id: int, request: Request):
    recipe_store: RecipeStore = request.app.state.recipe_store
    recipe: Recipe | None = await recipe_store.get(id)

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    return recipe
