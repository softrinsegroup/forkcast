from langchain_core.language_models import BaseChatModel
from unittest.mock import AsyncMock, MagicMock

from agent import classify, Intent, ClassifiedIntent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_model(intent: str, confidence: float) -> MagicMock:
    model = MagicMock(spec=BaseChatModel)
    chain = AsyncMock(
        return_value=ClassifiedIntent(intent=intent, confidence=confidence)
    )
    model.with_structured_output.return_value = chain
    return model


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------


async def test_classify_plan_intent():
    client = make_mock_model("plan", 0.95)
    result = await classify("plan my meals for the week", client)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.PLAN
    assert result.confidence == 0.95


async def test_classify_plan_intent_2():
    client = make_mock_model("plan", 0.8)
    result = await classify("what should I eat this week", client)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.PLAN
    assert result.confidence == 0.8


async def test_classify_chat_intent():
    client = make_mock_model("chat", 0.8)
    result = await classify("how many calories are in pasta?", client)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.CHAT
    assert result.confidence == 0.8


async def test_classify_low_confidence_still_returns():
    client = make_mock_model("chat", 0.4)
    result = await classify("hmm", client)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.CHAT
    assert result.confidence == 0.4


async def test_classify_confidence_boundary_zero():
    client = make_mock_model("chat", 0.0)
    result = await classify("hello", client)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.CHAT
    assert result.confidence == 0.0


async def test_classify_confidence_boundary_one():
    client = make_mock_model("plan", 1.0)
    result = await classify("make me a meal plan", client)
    assert isinstance(result, ClassifiedIntent)
    assert result.intent == Intent.PLAN
    assert result.confidence == 1.0
