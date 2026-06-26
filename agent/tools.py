from typing import Annotated
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command

from agent import MealPlanWorkflow, ParseRecipeWorkflow


def make_tools(args):
    @tool
    async def create_meal_plan() -> str:
        """Generate and persist a weekly meal plan from saved recipes."""
        result = await MealPlanWorkflow(
            args["model_agent"],
            args["recipe_store"],
            args["weekly_plan_store"],
            args["shopping_item_store"],
            args["prompt_store"],
            args["vector_store"],
        ).run()
        return "\n\n".join(result)

    @tool
    async def get_meal_plan() -> str:
        """TBD"""
        pass

    @tool
    async def parse_recipe_url(
        url: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        """Parse and preview a recipe from a URL. The user will confirm before it's saved."""
        reply, recipe = await ParseRecipeWorkflow(
            args["model_agent"], url, args["prompt_store"]
        ).run()
        content = "\n\n".join(reply) if isinstance(reply, list) else str(reply)

        return Command(
            update={"pending_recipe": recipe},
            messages=[ToolMessage(content=content, tool_call_id=tool_call_id)],
        )

    @tool
    async def get_shopping_list() -> str:
        """Get the shopping list for the current week's meal plan."""
        plan = await args["weekly_plan_store"].get_last_weekly_plan_recipe_ids()
        if not plan:
            return "No meal plan found. Ask me to create one first."

        items = await args["shopping_item_store"].get_by_weekly_plan(plan.id)
        if not items:
            return "No shopping items found for the current plan."

        lines = [
            f"- {item.ingredient_name} {item.amount} {item.unit}" for item in items
        ]
        return "**Shopping List**\n" + "\n".join(lines)
