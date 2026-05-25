import os
from contextlib import AsyncExitStack
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from langchain_chroma import Chroma
from langchain_voyageai import VoyageAIEmbeddings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langfuse import get_client as get_langfuse_client
from langfuse.langchain import CallbackHandler
import chromadb

from storage import (
    PromptStore,
    init_db,
    close_db,
    reconcile_recipes,
    RecipeStore,
    WeeklyPlanStore,
    ShoppingItemStore,
)
from .handlers import handle_message
from agent import create_graph


async def post_init(application: Application) -> None:
    # Init LangFuse
    langfuse = get_langfuse_client()
    if langfuse.auth_check():
        print("Initialized and authenticated LangFuse client")
        langfuse_handler = CallbackHandler()
        application.bot_data["langfuse_handler"] = langfuse_handler
    else:
        print("LangFuse authentication failed. Check your credentials and host.")
        langfuse_handler = None

    # Init Anthropic client
    model_classifier = ChatAnthropic(model="claude-haiku-4-5-20251001", max_tokens=64)
    application.bot_data["model_classifier"] = model_classifier
    model_agent = ChatAnthropic(model="claude-sonnet-4-6")
    application.bot_data["model_agent"] = model_agent
    print("Initialized Anthropic clients")

    # Init DB
    db = await init_db()
    application.bot_data["db"] = db
    recipe_store = RecipeStore(db)
    application.bot_data["recipe_store"] = recipe_store
    weekly_plan_store = WeeklyPlanStore(db)
    application.bot_data["weekly_plan_store"] = weekly_plan_store
    shopping_item_store = ShoppingItemStore(db)
    application.bot_data["shopping_item_store"] = shopping_item_store
    prompt_store = PromptStore(db)
    application.bot_data["prompt_store"] = prompt_store
    print("Initialized database")

    # Init Embeddings
    embeddings = VoyageAIEmbeddings(
        voyage_api_key=os.getenv("VOYAGE_API_KEY"),
        model="voyage-4",
    )
    application.bot_data["embeddings"] = embeddings
    print("Initialized embeddings")

    # Init Vector DB
    chroma_client = chromadb.HttpClient(
        host=os.getenv("CHROMA_HOST"), port=int(os.getenv("CHROMA_PORT"))
    )
    vector_store = Chroma(
        collection_name="recipes", embedding_function=embeddings, client=chroma_client
    )
    application.bot_data["vector_store"] = vector_store
    print("Initialized vector database")

    # Create checkpointer (kept alive for app lifetime via exit stack)
    exit_stack = AsyncExitStack()
    checkpointer = await exit_stack.enter_async_context(
        AsyncPostgresSaver.from_conn_string(os.getenv("DATABASE_URL"))
    )
    await checkpointer.setup()
    application.bot_data["checkpointer_exit_stack"] = exit_stack

    # Create recurring embedding reconcilation job (every 5 mins)
    application.job_queue.run_repeating(_reconcile_job, interval=300, first=10)

    # Create Graph
    graph = create_graph(
        model_classifier=model_classifier,
        model_agent=model_agent,
        recipe_store=recipe_store,
        weekly_plan_store=weekly_plan_store,
        shopping_item_store=shopping_item_store,
        prompt_store=prompt_store,
        vector_store=vector_store,
        checkpointer=checkpointer,
        langfuse_handler=langfuse_handler,
    )
    application.bot_data["graph"] = graph

    print("Meal Prep Agent is ready for your command 👨‍🍳")


async def post_shutdown(application: Application) -> None:
    # Close DB
    db = application.bot_data["db"]
    await close_db(db)

    # Close Checkpointer
    exit_stack = application.bot_data.get("checkpointer_exit_stack")
    if exit_stack:
        await exit_stack.aclose()


async def _reconcile_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await reconcile_recipes(
        context.application.bot_data["recipe_store"],
        context.application.bot_data["vector_store"],
    )


def run() -> None:
    load_dotenv()

    print("Connecting Telegram bot 🤖...")
    app = (
        Application.builder()
        .token(os.environ["TELEGRAM_BOT_TOKEN"])
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
