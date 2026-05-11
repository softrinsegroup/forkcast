from abc import ABC, abstractmethod

from models import PendingAction


class Workflow(ABC):
    @abstractmethod
    async def run(self) -> tuple[str, PendingAction | None]: ...
