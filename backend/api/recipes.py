from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_current_user, require_ingest_key
from storage import RecipeStore
from models import Recipe, RecipeCreate

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.post("/ingest", dependencies=[Depends(require_ingest_key)])
async def ingest(recipe: RecipeCreate, request: Request):
    """
    Machine ingest endpoint for the scraper CLI.
    Idempotent on source_url: a recipe already ingested from the same URL is
    skipped, not duplicated. Always 200 so the CLI can count skips without
    error handling. Embedding happens via the reconcile loop (embedded=false).
    """
    recipe_store: RecipeStore = request.app.state.recipe_store

    existing_id = await recipe_store.get_id_by_source_url(recipe.source_url)
    if existing_id is not None:
        return {"id": existing_id, "created": False}

    recipe_id = await recipe_store.create(recipe)
    return {"id": recipe_id, "created": True}


@router.get("/{id}", dependencies=[Depends(get_current_user)])
async def get(id: int, request: Request):
    recipe_store: RecipeStore = request.app.state.recipe_store
    recipe: Recipe | None = await recipe_store.get(id)

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    return recipe
