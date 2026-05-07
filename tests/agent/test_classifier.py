import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError

from agent import classify, Intent, ClassifiedIntent


def make_mock_client(intent: str, confidence: float) -> AsyncMock:
    tool_use_block = MagicMock()
    tool_use_block.input = {"intent": intent, "confidence": confidence}

    response = MagicMock()
    response.content = [tool_use_block]

    client = AsyncMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


async def test_classify_plan_intent():
    client = make_mock_client("plan", 0.95)
    result = await classify("plan my meals for the week", client)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.PLAN
    assert result.confidence == 0.95


async def test_classify_plan_intent_2():
    client = make_mock_client("plan", 0.8)
    result = await classify("what should I eat this week", client)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.PLAN
    assert result.confidence == 0.8


async def test_classify_chat_intent():
    client = make_mock_client("chat", 0.8)
    result = await classify("how many calories are in pasta?", client)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.CHAT
    assert result.confidence == 0.8


async def test_classify_low_confidence_still_returns():
    client = make_mock_client("chat", 0.4)
    result = await classify("hmm", client)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.CHAT
    assert result.confidence == 0.4


async def test_classify_confidence_boundary_zero():
    client = make_mock_client("chat", 0.0)
    result = await classify("hello", client)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.CHAT
    assert result.confidence == 0.0


async def test_classify_confidence_boundary_one():
    client = make_mock_client("plan", 1.0)
    result = await classify("make me a meal plan", client)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.PLAN
    assert result.confidence == 1.0


async def test_classify_calls_correct_model():
    client = make_mock_client("chat", 0.9)
    await classify("hello", client)
    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"


async def test_classify_forces_tool_choice():
    client = make_mock_client("chat", 0.9)
    await classify("hello", client)
    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "classify_intent"}


async def test_classify_passes_message_in_user_turn():
    client = make_mock_client("plan", 0.9)
    await classify("plan my meals", client)
    call_kwargs = client.messages.create.call_args.kwargs
    user_content = call_kwargs["messages"][0]["content"]
    assert "plan my meals" in user_content


async def test_classify_sets_max_tokens():
    client = make_mock_client("chat", 0.9)
    await classify("hello", client)
    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["max_tokens"] == 64


async def test_classify_includes_system_prompt():
    client = make_mock_client("chat", 0.9)
    await classify("hello", client)
    call_kwargs = client.messages.create.call_args.kwargs
    system = call_kwargs["system"]
    assert len(system) == 1
    assert system[0]["type"] == "text"
    assert system[0]["cache_control"] == {"type": "ephemeral"}


async def test_classify_raises_on_invalid_intent():
    client = make_mock_client("unknown_intent", 0.9)
    with pytest.raises(ValidationError):
        await classify("hello", client)
