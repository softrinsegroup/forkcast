from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_current_user
from models import Recipe, User, WeeklyPlan
from storage import RecipeStore, WeeklyPlanStore

router = APIRouter(prefix="/meal-plans", tags=["meal_plans"])


@router.get("/current")
async def current_meal_plan(request: Request, user: User = Depends(get_current_user)):
    # Get last meal plan
    weekly_plan_store: WeeklyPlanStore = request.app.state.weekly_plan_store
    weekly_plan: (
        WeeklyPlan | None
    ) = await weekly_plan_store.get_last_weekly_plan_recipe_ids(str(user.id))

    # No existing meal plan
    if not weekly_plan:
        raise HTTPException(status_code=404, detail="Meal Plan not found")

    # Fetch recipes for existing plan
    recipe_store: RecipeStore = request.app.state.recipe_store
    recipes_by_id: dict[int, Recipe] = {
        r.id: r for r in await recipe_store.get_by_ids(weekly_plan.recipe_ids)
    }
    recipes: list[Recipe] = [
        recipes_by_id[rid] for rid in weekly_plan.recipe_ids if rid in recipes_by_id
    ]

    return {
        "id": weekly_plan.id,
        "timestamp": weekly_plan.timestamp,
        "recipes": recipes,
        "shopping_items": weekly_plan.shopping_items,
    }
