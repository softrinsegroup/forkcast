from enum import Enum
from pydantic import BaseModel
from anthropic import AsyncAnthropic

from agent.prompts import CLASSIFY_INTENT_PROMPT
from agent.tools import CLASSIFY_INTENT_TOOL


class Intent(str, Enum):
    PLAN = "plan"
    CHAT = "chat"


class ClassifiedIntent(BaseModel):
    intent: Intent
    confidence: float


async def classify(message: str, client: AsyncAnthropic) -> ClassifiedIntent:
    resp = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=64,
        system=[
            {
                "type": "text",
                "text": CLASSIFY_INTENT_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[CLASSIFY_INTENT_TOOL],
        tool_choice={"type": "tool", "name": "classify_intent"},
        messages=[
            {
                "role": "user",
                "content": f"Classify this message: {message}",
            }
        ],
    )

    intent = resp.content[0].input["intent"]
    confidence = resp.content[0].input["confidence"]
    return ClassifiedIntent(intent=intent, confidence=confidence)
