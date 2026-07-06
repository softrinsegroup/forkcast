from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_current_user
from storage import RecipeStore
from models import Recipe, User

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("/{id}")
async def me(id: int, request: Request, user: User = Depends(get_current_user)):
    recipe_store: RecipeStore = request.app.state.recipe_store
    recipe: Recipe | None = await recipe_store.get(id)

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    return recipe
