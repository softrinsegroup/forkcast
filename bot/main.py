import os
from dotenv import load_dotenv
from telegram.ext import Application
from storage import init_db, close_db


async def post_init(application: Application) -> None:
    await init_db(os.getenv("DATABASE_PATH", "data/meal_prep.db"))


async def post_shutdown(application: Application) -> None:
    await close_db()


def run() -> None:
    load_dotenv()
    app = (
        Application.builder()
        .token(os.getenv("TELEGRAM_BOT_TOKEN", ""))
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.run_polling()
