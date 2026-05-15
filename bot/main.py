import os
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from telegram.ext import Application, MessageHandler, filters
import chromadb

from storage import init_db, close_db, RecipeStore, WeeklyPlanStore, ShoppingItemStore
from .handlers import handle_message


async def post_init(application: Application) -> None:
    # Init Anthropic client
    application.bot_data["anthropic_client"] = AsyncAnthropic()
    print("Initialized Anthropic client")

    # Init DB
    db = await init_db(os.getenv("DB_PATH", ".data/meal_prep.db"))
    application.bot_data["db"] = db
    application.bot_data["recipe_store"] = RecipeStore(db)
    application.bot_data["weekly_plan_store"] = WeeklyPlanStore(db)
    application.bot_data["shopping_item_store"] = ShoppingItemStore(db)
    print("Initialized database")

    # Init Vector DB
    chroma_client = chromadb.PersistentClient(os.getenv("VECTOR_DB_PATH", ".chroma"))
    application.bot_data["recipe_collection"] = chroma_client.get_or_create_collection(
        "recipes"
    )
    print("Initialized vector database")

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
