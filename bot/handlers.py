from telegram import Update
from telegram.ext import ContextTypes

from agent import route


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context._chat_id
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Classify and route to proper workflow
    user_message = update.message.text
    print("User:", user_message)

    # Call LLM
    bot_reply, pending_action = await route(
        user_message,
        context.bot_data["model_classifier"],
        context.bot_data["model_agent"],
        context.bot_data["recipe_store"],
        context.bot_data["weekly_plan_store"],
        context.bot_data["shopping_item_store"],
        context.bot_data["vector_store"],
    )
    print("Bot:", bot_reply)

    # Send reply
    await _send_reply(update, bot_reply)


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
