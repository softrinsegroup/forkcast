from langchain_anthropic import ChatAnthropic
from langchain_core.vectorstores import VectorStore

from agent.classifier import Intent, classify
from agent.workflows.chat import ChatWorkflow
from agent.workflows.meal_plan import MealPlanWorkflow
from agent.workflows.parse_recipe import ParseRecipeWorkflow
from storage import RecipeStore, WeeklyPlanStore, ShoppingItemStore
from utils import extract_url


async def route(
    message: str,
    model_classifier: ChatAnthropic,
    model_agent: ChatAnthropic,
    recipe_store: RecipeStore,
    weekly_plan_store: WeeklyPlanStore,
    shopping_item_store: ShoppingItemStore,
    vector_store: VectorStore,
) -> str:
    classified_intent = await classify(message, model_classifier)
    match classified_intent.intent:
        case Intent.PLAN:
            return await MealPlanWorkflow(
                model_agent,
                recipe_store,
                weekly_plan_store,
                shopping_item_store,
                vector_store,
            ).run()

        case Intent.PARSE_RECIPE:
            url = extract_url(message)
            return await ParseRecipeWorkflow(model_agent, url).run()

        case Intent.CHAT:
            return await ChatWorkflow().run()
