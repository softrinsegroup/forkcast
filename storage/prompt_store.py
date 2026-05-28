from asyncpg.connection import asyncpg

from models import Prompt, PromptType


class PromptStore:
    def __init__(self, db: asyncpg.connection.Connection):
        self.db = db

    async def get(self, type: PromptType) -> Prompt | None:
        row = await self.db.fetchrow(
            "SELECT * FROM prompts WHERE type = $1 AND active = TRUE", type
        )
        if row is None:
            return None
        return self._load_prompt(dict(row))

    def _load_prompt(self, row: dict) -> Prompt:
        return Prompt(
            id=row["id"],
            type=row["type"],
            prompt=row["prompt"],
            version=row["version"],
            active=row["active"],
            model=row["model"],
            notes=row["notes"],
            created_at=row["created_at"],
        )
