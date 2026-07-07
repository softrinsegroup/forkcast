import asyncpg
from cachetools import TTLCache

from models import Prompt, PromptType


class PromptStore:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self._cache = TTLCache(maxsize=16, ttl=300)

    async def get(self, type: PromptType) -> Prompt | None:
        # Return cached prompt if available
        if type in self._cache:
            return self._cache[type]

        # Fetch from DB
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM prompts WHERE type = $1 AND active = TRUE", type
            )
            if row is None:
                return None
            prompt = self._load_prompt(dict(row))

            # Store in cache
            self._cache[type] = prompt

            return prompt

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
