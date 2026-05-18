import os
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv
from telegram.ext import Application, MessageHandler, filters
from langchain_chroma import Chroma
from langchain_voyageai import VoyageAIEmbeddings
import chromadb

from storage import (
    init_db,
    close_db,
    reconcile_recipes,
    RecipeStore,
    WeeklyPlanStore,
    ShoppingItemStore,
)
from .handlers import handle_message


async def post_init(application: Application) -> None:
    # Init Anthropic client
    application.bot_data["model_classifier"] = ChatAnthropic(
        model="claude-haiku-4-5-20251001", max_tokens=64
    )
    application.bot_data["model_agent"] = ChatAnthropic(model="claude-sonnet-4-6")
    print("Initialized Anthropic clients")

    # Init DB
    db = await init_db(os.getenv("DB_PATH", ".data/meal_prep.db"))
    application.bot_data["db"] = db
    recipe_store = RecipeStore(db)
    application.bot_data["recipe_store"] = recipe_store
    application.bot_data["weekly_plan_store"] = WeeklyPlanStore(db)
    application.bot_data["shopping_item_store"] = ShoppingItemStore(db)
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

    # Reconcilation
    await reconcile_recipes(recipe_store, vector_store)

    print("Meal Prep Agent is ready for your command 👨‍🍳")


async def post_shutdown(application: Application) -> None:
    db = application.bot_data["db"]
    await close_db(db)


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
