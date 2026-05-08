from telegram import Update
from telegram.ext import ContextTypes

from agent import route


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context._chat_id
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Classify and route to proper workflow
    reply = await route(
        update.message,
        context.bot_data["anthropic_client"],
        context.bot_data["recipe_store"],
        context.bot_data["weekly_plan_store"],
        context.bot_data["shopping_item_store"],
    )

    for chunk in split_message(reply, limit=4096):
        await update.message.reply_text(chunk, parse_mode="Markdown")


def split_message(text: str, limit: int = 4096) -> list[str]:
    # Message is already under the limit, send it as whole
    if len(text) <= limit:
        return [text]

    chunks, curr_chunk, curr_len = [], [], 0
    for line in text.splitlines():
        line_len = len(line)
        if curr_len + line_len <= limit:
            # Add to current chunk if under the limit
            curr_chunk.append(line)
            curr_len += line_len
        else:
            # Append to split chunks and reset for next chunk
            chunks.append("\n".join(curr_chunk))
            curr_chunk.clear()
            curr_len = 0
    return chunks
