import pytest
from unittest.mock import AsyncMock, MagicMock

from langchain_core.language_models import BaseChatModel

from agent.workflows.chat import ChatInput, ChatWorkflow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_model(reply: str = "Here to help!") -> MagicMock:
    model = MagicMock(spec=BaseChatModel)
    chain = MagicMock()
    chain.ainvoke = AsyncMock(return_value=ChatInput(reply=reply))
    model.with_structured_output.return_value = chain
    return model


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workflow(mock_prompt_store):
    return ChatWorkflow(
        message="What can you help me with?",
        model=make_mock_model(),
        prompt_store=mock_prompt_store,
    )


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


async def test_run_returns_list(workflow):
    result = await workflow.run()
    assert isinstance(result, list)
    assert len(result) == 1


async def test_run_returns_llm_reply(mock_prompt_store):
    model = make_mock_model(reply="I can help you plan your meals for the week.")
    wf = ChatWorkflow(message="Hello", model=model, prompt_store=mock_prompt_store)
    result = await wf.run()
    assert result[0] == "I can help you plan your meals for the week."


async def test_run_passes_message_to_model(mock_prompt_store):
    model = make_mock_model()
    wf = ChatWorkflow(
        message="What recipes do you know?", model=model, prompt_store=mock_prompt_store
    )
    await wf.run()
    model.with_structured_output.assert_called_once_with(ChatInput)


async def test_run_fetches_chat_prompt(mock_prompt_store):
    from models import PromptType

    wf = ChatWorkflow(
        message="Hello", model=make_mock_model(), prompt_store=mock_prompt_store
    )
    await wf.run()
    mock_prompt_store.get.assert_called_once_with(PromptType.CHAT)
