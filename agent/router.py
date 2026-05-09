from anthropic import AsyncAnthropic

from agent.classifier import Intent, classify
from agent.workflows.chat import ChatWorkflow
from agent.workflows.meal_plan import MealPlanWorkflow
from agent.workflows.parse_recipe import ParseRecipeWorkflow
from storage import RecipeStore, WeeklyPlanStore, ShoppingItemStore
from utils import extract_url


async def route(
    message: str,
    client: AsyncAnthropic,
    recipe_store: RecipeStore,
    weekly_plan_store: WeeklyPlanStore,
    shopping_item_store: ShoppingItemStore,
) -> str:
    classified_intent = await classify(message, client)
    match classified_intent.intent:
        case Intent.PLAN:
            return await MealPlanWorkflow(
                client, recipe_store, weekly_plan_store, shopping_item_store
            ).run()

        case Intent.PARSE_RECIPE:
            url = extract_url(message)
            return await ParseRecipeWorkflow(client, recipe_store, url).run()

        case Intent.CHAT:
            return await ChatWorkflow().run()
