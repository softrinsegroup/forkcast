from enum import Enum
from pydantic import BaseModel
from anthropic import AsyncAnthropic


class Intent(str, Enum):
    PLAN = "plan"
    CHAT = "chat"


class ClassifiedIntent(BaseModel):
    intent: Intent
    confidence: float


async def classify(message: str, client: AsyncAnthropic) -> ClassifiedIntent:
    pass
