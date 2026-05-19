from langchain_core.language_models import BaseChatModel
from langchain_core.vectorstores import VectorStore
from langgraph.types import interrupt

from agent.classifier import Intent, classify
from agent.state import BotState
from agent.workflows.chat import ChatWorkflow
from agent.workflows.meal_plan import MealPlanWorkflow
from agent.workflows.parse_recipe import ParseRecipeWorkflow
from models import Recipe
from storage import RecipeStore, WeeklyPlanStore, ShoppingItemStore
from storage import embed_recipe
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
        reply, pending_action = await MealPlanWorkflow(
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
        reply, pending_action = await ParseRecipeWorkflow(model_agent, url).run()
        # TODO: handle missing pending action
        return {"reply": reply, "pending_recipe": pending_action.data["recipe"]}

    async def confirm_recipe_node(state: BotState) -> BotState:
        user_input = interrupt("Does your recipe look correct?")
        return {"user_message": user_input}

    async def save_recipe_node(state: BotState) -> BotState:
        user_message = state["user_message"].strip().lower()
        if user_message in ("yes", "y"):
            # Insert Recipe to DB
            recipe: Recipe = state["pending_recipe"]
            recipe_id = await recipe_store.create(recipe)
            # Missing id because it hasn't be inserted to the DB
            recipe.id = recipe_id

            try:
                # Embed Recipe
                await embed_recipe(vector_store, recipe)
                await recipe_store.update_embedded([recipe_id])
            except Exception as e:
                print(f"Warning: embedding failed for recipe_id={recipe_id}: {e}")

            return {
                "reply": f"I've saved your {recipe.name} Recipe for future meal plans."
            }

        return {"reply": "Cancelled saving your recipe."}

    async def chat_node(state: BotState) -> BotState:
        reply, pending_action = await ChatWorkflow().run()
        return {"reply": reply}

    async def intent_router(state: BotState) -> str:
        match state["intent"].intent:
            case Intent.PLAN:
                return "meal_plan_node"
            case Intent.PARSE_RECIPE:
                return "parse_recipe_node"
            case Intent.CHAT:
                return "chat_node"

    async def confirm_recipe_router(state: BotState) -> str:
        user_message = state["user_message"].strip().lower()
        if user_message in ("yes", "y"):
            return "save_recipe_node"

        # End the workflow if not confirming
        return "end"
