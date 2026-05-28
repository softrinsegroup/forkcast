from langchain_core.language_models import BaseChatModel
from unittest.mock import AsyncMock, MagicMock

from agent import classify, Intent, ClassifiedIntent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_model(intent: str, confidence: float) -> MagicMock:
    model = MagicMock(spec=BaseChatModel)
    model.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=ClassifiedIntent(intent=intent, confidence=confidence)
    )
    return model


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------


async def test_classify_plan_intent(mock_prompt_store):
    client = make_mock_model("plan", 0.95)
    result = await classify("plan my meals for the week", client, mock_prompt_store)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.PLAN
    assert result.confidence == 0.95


async def test_classify_plan_intent_2(mock_prompt_store):
    client = make_mock_model("plan", 0.8)
    result = await classify("what should I eat this week", client, mock_prompt_store)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.PLAN
    assert result.confidence == 0.8


async def test_classify_chat_intent(mock_prompt_store):
    client = make_mock_model("chat", 0.8)
    result = await classify("how many calories are in pasta?", client, mock_prompt_store)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.CHAT
    assert result.confidence == 0.8


async def test_classify_low_confidence_still_returns(mock_prompt_store):
    client = make_mock_model("chat", 0.4)
    result = await classify("hmm", client, mock_prompt_store)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.CHAT
    assert result.confidence == 0.4


async def test_classify_confidence_boundary_zero(mock_prompt_store):
    client = make_mock_model("chat", 0.0)
    result = await classify("hello", client, mock_prompt_store)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.CHAT
    assert result.confidence == 0.0


async def test_classify_confidence_boundary_one(mock_prompt_store):
    client = make_mock_model("plan", 1.0)
    result = await classify("make me a meal plan", client, mock_prompt_store)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.PLAN
    assert result.confidence == 1.0


async def test_classify_llm_failure_falls_back_to_chat(mock_prompt_store):
    # The classifier is the first node for every message. Without the fallback, any
    # Anthropic API error (rate limit, timeout, bad structured output) would silence the
    # bot entirely. The fallback routes to CHAT so the user still gets a response.
    model = MagicMock(spec=BaseChatModel)
    model.with_structured_output.return_value.ainvoke = AsyncMock(
        side_effect=RuntimeError("API unavailable")
    )
    result = await classify("plan my week", model, mock_prompt_store)
    assert result.intent == Intent.CHAT
    assert result.confidence == 0.0
