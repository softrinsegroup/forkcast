from datetime import date

from storage.recipe_store import RecipeStore
from storage.weekly_plan_store import WeeklyPlanStore


def meal_plan_workflow() -> str:
    # Fetch all recipes
    recipes = RecipeStore()
    recipes.get_all()

    # Fetch previous weekly_plan
    weekly_plans = WeeklyPlanStore()
    weekly_plans.get_nearest_by_date(date.today())

    # Call LLM to get new plan with minimal overlap

    # Validate recipe_ids

    # Aggregate ingredients

    # Create shopping_items

    # Create weekly_plan
