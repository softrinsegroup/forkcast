import pytest
from unittest.mock import AsyncMock, MagicMock
from dotenv import load_dotenv

from storage import PromptStore

load_dotenv(".env.test", override=True)


@pytest.fixture
def mock_prompt_store():
    store = MagicMock(spec=PromptStore)
    store.get = AsyncMock(
        return_value="You are a helpful meal prep assistant. Help users plan meals and add recipes."
    )
    return store
