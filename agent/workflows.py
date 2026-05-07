from datetime import date
from anthropic import AsyncAnthropic

from agent.prompts import MEAL_PLAN_PROMPT
from agent.tools import CREATE_MEAL_PLAN_TOOL
from storage.recipe_store import RecipeStore
from storage.weekly_plan_store import WeeklyPlanStore


async def meal_plan_workflow(client: AsyncAnthropic) -> str:
    # Fetch all recipes
    recipe_store = RecipeStore()
    recipes = {r.id: {"name": r.name, "tags": r.tags} for r in recipe_store.get_all()}

    # Fetch previous weekly_plan
    weekly_plan_store = WeeklyPlanStore()
    prev_weekly_plan = weekly_plan_store.get_last_weekly_plan_recipe_ids()
    prev_recipe_ids = (
        prev_weekly_plan.recipe_ids if prev_weekly_plan is not None else []
    )

    # Call LLM to get new plan with minimal overlap
    llm_resp = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=[
            {
                "type": "text",
                "text": MEAL_PLAN_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[CREATE_MEAL_PLAN_TOOL],
        tool_choice={"type": "tool", "name": "create_meal_plan"},
        messages=[
            {
                "role": "user",
                "content": "",
            }
        ],
    )

    # Validate recipe_ids

    # Aggregate ingredients

    # Create shopping_items

    # Create weekly_plan
