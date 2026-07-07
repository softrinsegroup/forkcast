from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class PromptType(str, Enum):
    AGENT = "agent"
    PLAN = "plan"
    PARSE_RECIPE = "parse_recipe"
    CHAT = "chat"


class Prompt(BaseModel):
    id: int
    type: PromptType
    prompt: str
    version: int
    active: bool
    model: str | None
    notes: str | None
    created_at: datetime
