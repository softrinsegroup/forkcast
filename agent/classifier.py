from enum import Enum
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from models import PromptType
from storage import PromptStore


class Intent(str, Enum):
    PLAN = "plan"
    PARSE_RECIPE = "parse_recipe"
    CHAT = "chat"


class ClassifiedIntent(BaseModel):
    intent: Intent = Field(description="Intent of the message")
    confidence: float = Field(
        description="Confidence of the classification from 0.0 to 1.0"
    )


async def classify(
    message: str, model: BaseChatModel, prompt_store: PromptStore
) -> ClassifiedIntent:
    try:
        prompt = await prompt_store.get(PromptType.CLASSIFIER)
        messages = [
            SystemMessage(
                content=prompt,
                additional_kwargs={"cache_control": {"type": "ephemeral"}},
            ),
            HumanMessage(content=f"Classify this message: {message}"),
        ]
        intent: ClassifiedIntent = await model.with_structured_output(
            ClassifiedIntent
        ).ainvoke(messages)
        print(f"Intent: {intent.intent} {intent.confidence}")
        return intent
    except Exception as e:
        print(f"[classify] Error: {e}, falling back to CHAT")
        return ClassifiedIntent(intent=Intent.CHAT, confidence=0.0)
