from langchain_core.language_models import BaseChatModel
from langchain_core.vectorstores import VectorStore
from agent.classifier import classify
from agent.state import BotState
from agent.workflows.meal_plan import MealPlanWorkflow
from agent.workflows.parse_recipe import ParseRecipeWorkflow
from storage import RecipeStore, WeeklyPlanStore, ShoppingItemStore
from utils import extract_url


def create_graph(
    model_classifier: BaseChatModel,
    model_agent: BaseChatModel,
    recipe_store: RecipeStore,
    weekly_plan_store: WeeklyPlanStore,
    shopping_item_store: ShoppingItemStore,
    vector_store: VectorStore,
):
    async def classify_node(state: BotState) -> BotState:
        user_msg = state["user_message"]
        result = await classify(user_msg, model_classifier)
        return {"intent": result}

    async def meal_plan_node(state: BotState) -> BotState:
        reply = await MealPlanWorkflow(
            model_agent,
            recipe_store,
            weekly_plan_store,
            shopping_item_store,
            vector_store,
        ).run()
        return {"reply": reply}

    async def parse_recipe_node(state: BotState) -> BotState:
        user_msg = state["user_message"]
        url = extract_url(user_msg)
        reply = await ParseRecipeWorkflow(model_agent, url).run()
        return {"reply": reply}
