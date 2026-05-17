from bot.handlers import _split_message


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
