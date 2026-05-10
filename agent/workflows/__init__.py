from typing import Protocol

from models import PendingAction


class Workflow(Protocol):
    async def run(self) -> tuple[str, PendingAction | None]: ...
