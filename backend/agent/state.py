from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

from models import Recipe


class BotState(TypedDict):
    user_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    user_message: str
    pending_recipe: Recipe | None
