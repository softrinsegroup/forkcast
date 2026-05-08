import os
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from telegram.ext import Application

from storage import init_db, close_db, RecipeStore, WeeklyPlanStore, ShoppingItemStore


async def post_init(application: Application) -> None:
    application.bot_data["anthropic_client"] = AsyncAnthropic()
    print("Initialized Anthropic client")

    db = await init_db(os.getenv("DATABASE_PATH", "data/meal_prep.db"))
    application.bot_data["db"] = db
    application.bot_data["recipe_store"] = RecipeStore(db)
    application.bot_data["weekly_plan_store"] = WeeklyPlanStore(db)
    application.bot_data["shopping_item_store"] = ShoppingItemStore(db)
    print("Initialized data stores")

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
    app.run_polling()
