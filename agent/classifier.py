from enum import Enum
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field


CLASSIFY_INTENT_PROMPT = """
You are an intent classifier for a Meal Planning Assistant. Classify the user's message into exactly one of the following intents:

Intents:
- `parse_recipe` — user wants to add a recipe from a URL (e.g. "add this recipe https://...", "save this recipe https://...")
- `plan` — user wants to generate a meal plan for the week (e.g. "plan my meals", "what should I eat this week", "make me a meal plan")
- `chat` — anything else: questions, feedback, greetings, unclear requests

Set `confidence` between 0.0 and 1.0 — use lower values when the message is ambiguous.
"""


class Intent(str, Enum):
    PLAN = "plan"
    PARSE_RECIPE = "parse_recipe"
    CHAT = "chat"


class ClassifiedIntent(BaseModel):
    intent: Intent = Field(description="Intent of the message")
    confidence: float = Field(
        description="Confidence of the classification from 0.0 to 1.0"
    )


classify_prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessage(
            content=CLASSIFY_INTENT_PROMPT,
            additional_kwargs={"cache_control": {"type": "ephemeral"}},
        ),
        ("human", "Classify this message: {message}"),
    ]
)


async def classify(message: str, model: BaseChatModel) -> ClassifiedIntent:
    try:
        chain = classify_prompt | model.with_structured_output(ClassifiedIntent)
        intent: ClassifiedIntent = await chain.ainvoke({"message": message})
        print(f"Intent: {intent.intent} {intent.confidence}")
        return intent
    except Exception as e:
        print(f"[classify] Error: {e}, falling back to CHAT")
        return ClassifiedIntent(intent=Intent.CHAT, confidence=0.0)
