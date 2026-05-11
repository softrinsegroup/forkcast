from agent.workflows import Workflow
from models import PendingAction


class ChatWorkflow(Workflow):
    async def run(self) -> tuple[str, PendingAction | None]:
        return (
            "I can help you plan meals and add recipes. "
            "Try saying: 'Plan my meals', 'What should I eat this week', 'Make me a meal plan'"
        ), None
