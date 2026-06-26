from typing import Annotated
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langchain_core.vectorstores import VectorStore
from langgraph.types import Command

from agent import MealPlanWorkflow, ParseRecipeWorkflow
from storage import PromptStore, RecipeStore, ShoppingItemStore, WeeklyPlanStore


def make_tools(
    model_agent: BaseChatModel,
    recipe_store: RecipeStore,
    weekly_plan_store: WeeklyPlanStore,
    shopping_item_store: ShoppingItemStore,
    prompt_store: PromptStore,
    vector_store: VectorStore,
):
    @tool
    async def create_meal_plan() -> str:
        """Generate and persist a weekly meal plan from saved recipes."""
        result = await MealPlanWorkflow(
            model_agent,
            recipe_store,
            weekly_plan_store,
            shopping_item_store,
            prompt_store,
            vector_store,
        ).run()
        return "\n\n".join(result)

    @tool
    async def get_meal_plan() -> str:
        """Get the current week's meal plan."""
        plan = await weekly_plan_store.get_last_weekly_plan_recipe_ids()
        if not plan:
            return "No meal plan found."

        recipes = await recipe_store.get_by_ids(plan.recipe_ids)
        lines = [f"**Week of {plan.timestamp.isoformat()}**"]
        for i, r in enumerate(recipes):
            lines.append(f"{i + 1}. {r.name} ({', '.join(r.tags)})")
        return "\n".join(lines)

    @tool
    async def parse_recipe_url(
        url: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        """Parse and preview a recipe from a URL. The user will confirm before it's saved."""
        reply, recipe = await ParseRecipeWorkflow(model_agent, url, prompt_store).run()
        content = "\n\n".join(reply) if isinstance(reply, list) else str(reply)

        return Command(
            update={
                "pending_recipe": recipe,
                "messages": [ToolMessage(content=content, tool_call_id=tool_call_id)],
            },
        )

    @tool
    async def get_shopping_list() -> str:
        """Get the shopping list for the current week's meal plan."""
        plan = await weekly_plan_store.get_last_weekly_plan_recipe_ids()
        if not plan:
            return "No meal plan found. Ask me to create one first."

        items = await shopping_item_store.get_by_weekly_plan(plan.id)
        if not items:
            return "No shopping items found for the current plan."

        lines = [
            f"- {item.ingredient_name} {item.amount} {item.unit}" for item in items
        ]
        return "**Shopping List**\n" + "\n".join(lines)

    return [create_meal_plan, get_meal_plan, parse_recipe_url, get_shopping_list]
