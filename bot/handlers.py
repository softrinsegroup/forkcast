from telegram import Update
from telegram.ext import ContextTypes

from agent import route
from agent.workflows import PendingAction
from models import Recipe
from storage import RecipeStore, embed_recipe


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context._chat_id
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Classify and route to proper workflow
    user_message = update.message.text
    print("User:", user_message)

    # Handle PendingAction and stop if handled
    if await _handle_pending_action(update, context, user_message):
        return

    # Call LLM
    bot_reply, pending_action = await route(
        user_message,
        context.bot_data["model_classifier"],
        context.bot_data["model_agent"],
        context.bot_data["recipe_store"],
        context.bot_data["weekly_plan_store"],
        context.bot_data["shopping_item_store"],
    )
    print("Bot:", bot_reply)

    # Handle multi-step actions
    _store_pending_action(pending_action, context)

    # Send reply
    await _send_reply(update, bot_reply)


def _store_pending_action(
    action: PendingAction | None, context: ContextTypes.DEFAULT_TYPE
) -> None:
    # No pending action, do nothing
    if action is None:
        return

    # Store pending action in context
    context.user_data["pending_action"] = action


async def _handle_pending_action(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user_message: str
) -> bool:
    if "pending_action" in context.user_data:
        pending_action: PendingAction = context.user_data.pop("pending_action")
        match pending_action.type:
            case "confirm_recipe":
                bot_reply = await _handle_confirm_recipe_message(
                    user_message, context, pending_action
                )
                await _send_reply(update, bot_reply)
                return True

            case _:
                print(f"Unhandled PendingAction: {pending_action.type}")
                return False

    return False


async def _handle_confirm_recipe_message(
    user_message: str, context: ContextTypes.DEFAULT_TYPE, pending_action: PendingAction
) -> str:
    user_message = user_message.strip().lower()
    if user_message in ("yes", "y"):
        # Save Recipe to DB
        recipe_store: RecipeStore = context.bot_data["recipe_store"]
        # Missing id because it hasn't be inserted to the DB
        recipe: Recipe = pending_action.data["recipe"]
        recipe_id = await recipe_store.create(recipe)
        recipe.id = recipe_id

        # Embed Recipe
        vector_store = context.bot_data["vector_store"]
        try:
            await embed_recipe(vector_store, recipe)
            await recipe_store.update_embedded([recipe_id])
        except Exception as e:
            print(f"Warning: embedding failed for recipe_id={recipe_id}: {e}")

        return f"I've saved your {recipe.name} Recipe for future meal plans."

    return "Cancelled saving your recipe."


def _split_message(text: str, limit: int = 4096) -> list[str]:
    # Message is already under the limit, send it as whole
    if len(text) <= limit:
        return [text]

    chunks, curr_chunk, curr_len = [], [], 0
    for line in text.splitlines():
        line_len = len(line)
        if curr_len + line_len > limit:
            # Putting current line goes over the limit, start new chunk
            chunks.append("\n".join(curr_chunk))
            curr_chunk.clear()
            curr_len = 0

        # Append to chunk and track length
        curr_chunk.append(line)
        curr_len += line_len + 1

    # Append last chunk if not empty
    if curr_len > 0:
        chunks.append("\n".join(curr_chunk))

    return chunks


async def _send_reply(update: Update, bot_reply: str):
    for chunk in _split_message(bot_reply, limit=4096):
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(chunk)
