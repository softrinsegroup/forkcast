import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from dotenv import load_dotenv

from models import Prompt, PromptType
from storage import PromptStore

load_dotenv(".env.test", override=True)


@pytest.fixture
def mock_prompt_store():
    store = MagicMock(spec=PromptStore)
    store.get = AsyncMock(
        return_value=Prompt(
            id=1,
            type=PromptType.CHAT,
            prompt="You are a helpful meal prep assistant. Help users plan meals and add recipes.",
            version=1,
            active=True,
            model="claude-haiku-4-5-20251001",
            notes=None,
            created_at=datetime(2026, 1, 1),
        )
    )
    return store
