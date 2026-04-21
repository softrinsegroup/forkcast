import json
from datetime import datetime, date
from typing import Protocol
from models.domain import WeeklyPlan
from storage.db import get_db


class IWeeklyPlanStore(Protocol):
    async def create(self, plan: WeeklyPlan) -> None: ...
    async def get(self, id: int) -> WeeklyPlan | None: ...
    async def get_all(self) -> list[WeeklyPlan]: ...
    async def update(self, plan: WeeklyPlan) -> None: ...
    async def delete(self, id: int) -> None: ...


class WeeklyPlanStore:
    async def create(self, plan: WeeklyPlan) -> None:
        db = get_db()
        await db.execute(
            "INSERT INTO weekly_plans (id, timestamp, recipe_ids, created_at) VALUES (?, ?, ?, ?)",
            (
                plan.id,
                plan.timestamp.isoformat(),
                json.dumps(plan.recipe_ids),
                plan.created_at.isoformat(),
            ),
        )
        await db.commit()

    async def get(self, id: int) -> WeeklyPlan | None:
        db = get_db()
        async with db.execute("SELECT * FROM weekly_plans WHERE id = ?", (id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return self._row_to_plan(row)

    async def get_all(self) -> list[WeeklyPlan]:
        db = get_db()
        async with db.execute("SELECT * FROM weekly_plans") as cur:
            rows = await cur.fetchall()
        return [self._row_to_plan(row) for row in rows]

    async def update(self, plan: WeeklyPlan) -> None:
        db = get_db()
        await db.execute(
            "UPDATE weekly_plans SET timestamp=?, recipe_ids=?, created_at=? WHERE id=?",
            (
                plan.timestamp.isoformat(),
                json.dumps(plan.recipe_ids),
                plan.created_at.isoformat(),
                plan.id,
            ),
        )
        await db.commit()

    async def delete(self, id: int) -> None:
        db = get_db()
        await db.execute("DELETE FROM weekly_plans WHERE id = ?", (id,))
        await db.commit()

    @staticmethod
    def _row_to_plan(row) -> WeeklyPlan:
        return WeeklyPlan(
            id=row["id"],
            timestamp=date.fromisoformat(row["timestamp"]),
            recipe_ids=json.loads(row["recipe_ids"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
