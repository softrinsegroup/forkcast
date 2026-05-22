from unittest.mock import AsyncMock, MagicMock

from bot.handlers import _split_message, handle_message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_update(text: str = "hello") -> MagicMock:
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def make_mock_context(graph: MagicMock) -> MagicMock:
    context = MagicMock()
    context._chat_id = 123
    context.bot.send_chat_action = AsyncMock()
    context.bot_data = {"graph": graph}
    return context


def make_mock_graph(
    result: dict | None = None, raises: Exception | None = None
) -> MagicMock:
    graph = MagicMock()
    snapshot = MagicMock()
    snapshot.next = None
    snapshot.tasks = []
    graph.aget_state = AsyncMock(return_value=snapshot)
    if raises is not None:
        graph.ainvoke = AsyncMock(side_effect=raises)
    else:
        graph.ainvoke = AsyncMock(return_value=result or {"reply": ["ok"]})
    return graph


# ---------------------------------------------------------------------------
# handle_message
# ---------------------------------------------------------------------------


async def test_handle_message_graph_crash_sends_error_reply():
    # The top-level try/except is the last line of defense. Any uncaught exception
    # from the graph — LLM failure, DB drop, unhandled edge case — must produce a
    # user-facing reply instead of silence. Without this boundary, the user never knows
    # something went wrong.
    graph = make_mock_graph(raises=RuntimeError("graph exploded"))
    update = make_mock_update()
    context = make_mock_context(graph)

    await handle_message(update, context)

    all_args = [
        str(call.args[0])
        for call in update.message.reply_text.call_args_list
        if call.args
    ]
    assert "Sorry, something went wrong. Please try again." in all_args


async def test_handle_message_none_reply_does_not_crash():
    # BotState.reply is str | list[str] | None. A node setting reply=None is valid state.
    # Before `result.get("reply") or [""]`, this caused TypeError in _send_reply because
    # you can't iterate None. The fix must ensure reply_text is still called.
    graph = make_mock_graph(result={"reply": None})
    update = make_mock_update()
    context = make_mock_context(graph)

    await handle_message(update, context)

    update.message.reply_text.assert_called()


# ---------------------------------------------------------------------------
# _split_message
# ---------------------------------------------------------------------------


def test_short_message_returns_single_chunk():
    result = _split_message("hello", limit=4096)
    assert result == ["hello"]


def test_message_at_limit_returns_single_chunk():
    text = "a" * 4096
    result = _split_message(text, limit=4096)
    assert result == [text]


def test_long_message_produces_multiple_chunks():
    line = "a" * 100
    text = "\n".join([line] * 50)  # 5000 chars across 50 lines
    result = _split_message(text, limit=4096)
    assert len(result) > 1


def test_each_chunk_within_limit():
    line = "a" * 100
    text = "\n".join([line] * 50)
    limit = 4096
    result = _split_message(text, limit=limit)
    for chunk in result:
        assert len(chunk) <= limit


def test_no_content_lost_across_chunks():
    lines = [f"line {i}" for i in range(200)]
    text = "\n".join(lines)
    chunks = _split_message(text, limit=500)
    rejoined = "\n".join(chunks)
    assert rejoined == text


def test_custom_limit_respected():
    text = "short line\n" * 10
    result = _split_message(text, limit=20)
    for chunk in result:
        assert len(chunk) <= 20


def test_empty_string_returns_single_empty_chunk():
    result = _split_message("", limit=4096)
    assert result == [""]


def test_single_line_no_newlines():
    text = "no newlines here"
    result = _split_message(text, limit=4096)
    assert result == [text]
