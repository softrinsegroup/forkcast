from langchain_anthropic import ChatAnthropic

from agent.classifier import Intent, classify
from agent.workflows.chat import ChatWorkflow
from agent.workflows.meal_plan import MealPlanWorkflow
from agent.workflows.parse_recipe import ParseRecipeWorkflow
from storage import RecipeStore, WeeklyPlanStore, ShoppingItemStore
from utils import extract_url


async def route(
    message: str,
    model_classifier: ChatAnthropic,
    model_primary: ChatAnthropic,
    recipe_store: RecipeStore,
    weekly_plan_store: WeeklyPlanStore,
    shopping_item_store: ShoppingItemStore,
) -> str:
    classified_intent = await classify(message, model_classifier)
    match classified_intent.intent:
        case Intent.PLAN:
            return await MealPlanWorkflow(
                model_primary, recipe_store, weekly_plan_store, shopping_item_store
            ).run()

        case Intent.PARSE_RECIPE:
            url = extract_url(message)
            return await ParseRecipeWorkflow(model_primary, url).run()

        case Intent.CHAT:
            return await ChatWorkflow().run()
