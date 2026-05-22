from telegram import Update
from telegram.ext import ContextTypes
from langgraph.types import Command


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        chat_id = context._chat_id
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        # Show user message
        user_message = update.message.text
        print("User:", user_message)

        # thread_id is equivalent to the unique run_id
        config = {"configurable": {"thread_id": chat_id}}
        graph = context.bot_data["graph"]

        snapshot = await graph.aget_state(config)
        if snapshot.next:
            # Resume interrupted state (e.g. confirm_recipe)
            result = await graph.ainvoke(Command(resume=user_message), config=config)
        else:
            # Non-interrupted state
            result = await graph.ainvoke(
                {"chat_id": chat_id, "user_message": user_message}, config=config
            )

        # Wrap in list if needed
        bot_reply = result.get("reply") or [""]
        if isinstance(bot_reply, str):
            bot_reply = [bot_reply]

        # If graph is now paused at an interrupt, append its prompt to the reply
        new_snapshot = await graph.aget_state(config)
        for task in new_snapshot.tasks:
            for interrupt in task.interrupts:
                # Append interrupt messages to existing reply
                bot_reply.append(interrupt.value)

        print("Bot:", bot_reply)
        await _send_reply(update, bot_reply)
    except Exception as e:
        print(f"[handle_message] Unhandled exception: {e}")
        await _send_reply(update, ["Sorry, something went wrong. Please try again."])


async def _send_reply(update: Update, bot_reply: list[str]):
    for reply in bot_reply:
        for chunk in _split_message(reply, limit=4096):
            try:
                await update.message.reply_text(chunk, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(chunk)


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
