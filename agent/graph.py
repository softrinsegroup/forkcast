from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.vectorstores import VectorStore
from langfuse.langchain import CallbackHandler
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt
from langgraph.graph import StateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.constants import START, END
from langgraph.prebuilt import ToolNode

from agent.state import BotState
from agent.tools import make_tools
from models import PromptType, Recipe
from storage import PromptStore, RecipeStore, WeeklyPlanStore, ShoppingItemStore
from storage import embed_recipe


# Max number of Agent turns
MAX_TURNS = 10


def create_graph(
    model_agent: BaseChatModel,
    recipe_store: RecipeStore,
    weekly_plan_store: WeeklyPlanStore,
    shopping_item_store: ShoppingItemStore,
    prompt_store: PromptStore,
    vector_store: VectorStore,
    checkpointer: BaseCheckpointSaver,
    langfuse_handler: CallbackHandler | None,
) -> CompiledStateGraph:
    # Inject tools to model
    tools = make_tools(
        model_agent=model_agent,
        recipe_store=recipe_store,
        weekly_plan_store=weekly_plan_store,
        shopping_item_store=shopping_item_store,
        prompt_store=prompt_store,
        vector_store=vector_store,
    )
    model_with_tools = model_agent.bind_tools(tools)

    async def agent_node(state: BotState) -> BotState:
        """Primary agent react loop."""
        prompt = await prompt_store.get(PromptType.AGENT)
        sys = SystemMessage(content=prompt.prompt)
        resp = await model_with_tools.ainvoke([sys] + state["messages"])
        return {"messages": [resp]}

    def should_continue(state: BotState) -> str:
        """Determines if the end state has been achieved."""
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            # Check number of agent turns
            turns = sum(1 for m in state["messages"] if isinstance(m, AIMessage))
            print(f"Current Agent turns: {turns}")
            if turns >= MAX_TURNS:
                print("Exceeded Agent MAX_TURNS, exiting loop")
                return END

            # Execute tool calls
            return "tools"

        # Last message was not a tool call
        return END

    def after_tools(state: BotState) -> str:
        """Execution middleware after tool calls."""
        if state.get("pending_recipe"):
            return "confirm_recipe"

        return "agent"

    async def confirm_recipe(state: BotState) -> BotState:
        """Prompts the user to confirm the parsed recipe."""
        user_input = interrupt(
            'Does your recipe look correct?\nRespond with "yes" or "no".'
        )
        return {"user_message": user_input}

    def after_confirm_recipe(state: BotState) -> str:
        user_message = state["user_message"].strip().lower()
        if user_message in ("yes", "y"):
            return "save_recipe"

        # User did not confirm, discard it
        return "discard_recipe"

    async def discard_recipe(state: BotState) -> BotState:
        reply = "Got it, I won't save the recipe."
        return {"messages": [AIMessage(content=reply)], "pending_recipe": None}

    async def save_recipe(state: BotState) -> BotState:
        # Insert Recipe to DB
        recipe: Recipe = state["pending_recipe"]
        recipe_id = await recipe_store.create(recipe)
        # Hydrate missing id because it hasn't be inserted to the DB
        recipe.id = recipe_id

        # Embed Recipe
        try:
            await embed_recipe(vector_store, recipe)
            await recipe_store.update_embedded([recipe_id])
        except Exception as e:
            # Swallow exception, reconciliation will try to embed later
            print(f"Warning: embedding failed for recipe_id={recipe_id}: {e}")

        reply = f"I've saved your {recipe.name} Recipe for future meal plans."
        return {"messages": [AIMessage(content=reply)], "pending_recipe": None}

    # Build graph
    workflow = StateGraph(BotState)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("agent", agent_node)
    workflow.add_node("confirm_recipe", confirm_recipe)
    workflow.add_node("discard_recipe", discard_recipe)
    workflow.add_node("save_recipe", save_recipe)

    # Add edges
    # agent → should_continue → tools (if tool_calls) or END (if plain text)
    # tools → after_tools → confirm_recipe (if pending_recipe) or agent (loop back)
    # confirm_recipe → after_confirm_recipe → save_recipe or discard_recipe
    # save_recipe → END, discard_recipe → END
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_conditional_edges("tools", after_tools)
    workflow.add_conditional_edges("confirm_recipe", after_confirm_recipe)
    workflow.add_edge("save_recipe", END)
    workflow.add_edge("discard_recipe", END)

    callbacks = [langfuse_handler] if langfuse_handler else []
    return workflow.compile(checkpointer=checkpointer).with_config(
        {"callbacks": callbacks}
    )
