import json
from datetime import datetime, date
from typing import Protocol
import aiosqlite

from models import WeeklyPlan, ShoppingItem
from storage.db import transaction
import utils.date


class IWeeklyPlanStore(Protocol):
    async def create(self, plan: WeeklyPlan) -> None: ...
    async def get(self, id: int) -> WeeklyPlan | None: ...
    async def update(self, plan: WeeklyPlan) -> None: ...
    async def delete(self, id: int) -> None: ...


class WeeklyPlanStore:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def create(self, plan: WeeklyPlan) -> int:
        async with transaction(self.db):
            # Insert WeeklyPlan
            async with self.db.execute(
                "INSERT INTO weekly_plans (timestamp, recipe_ids, created_at) VALUES (?, ?, ?)",
                (
                    plan.timestamp.isoformat(),
                    json.dumps(plan.recipe_ids),
                    plan.created_at.isoformat(),
                ),
            ) as cur:
                weekly_plan_id = cur.lastrowid
            if weekly_plan_id is None:
                raise RuntimeError("INSERT into weekly_plans returned no rowid")

            # Insert ShoppingItems
            for item in plan.shopping_items:
                await self.db.execute(
                    "INSERT INTO shopping_items (weekly_plan_id, ingredient_name, unit, amount) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        weekly_plan_id,
                        item.ingredient_name,
                        item.unit,
                        item.amount,
                    ),
                )

            print(f"WeeklyPlan created for {plan.timestamp.isoformat()}")

            return weekly_plan_id

    async def get(self, id: int) -> WeeklyPlan | None:
        async with self.db.execute(
            "SELECT * FROM weekly_plans WHERE id = ?", (id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return await self._parse_weekly_plan(row)

    async def get_last_weekly_plan_recipe_ids(self) -> WeeklyPlan | None:
        last_monday = utils.date.last_monday()

        async with self.db.execute(
            "SELECT * FROM weekly_plans WHERE timestamp = ? LIMIT 1",
            (last_monday.isoformat(),),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return await self._parse_weekly_plan(row)

    async def update(self, plan: WeeklyPlan) -> None:
        async with transaction(self.db):
            await self.db.execute(
                "UPDATE weekly_plans SET timestamp=?, recipe_ids=?, created_at=? WHERE id=?",
                (
                    plan.timestamp.isoformat(),
                    json.dumps(plan.recipe_ids),
                    plan.created_at.isoformat(),
                    plan.id,
                ),
            )

    async def delete(self, id: int) -> None:
        async with transaction(self.db):
            await self.db.execute("DELETE FROM weekly_plans WHERE id = ?", (id,))

    async def _parse_weekly_plan(self, row) -> WeeklyPlan:
        async with self.db.execute(
            "SELECT * FROM shopping_items WHERE weekly_plan_id = ?", (row["id"],)
        ) as cur:
            item_rows = await cur.fetchall()
        shopping_items = [
            ShoppingItem(
                id=r["id"],
                weekly_plan_id=r["weekly_plan_id"],
                ingredient_name=r["ingredient_name"],
                unit=r["unit"],
                amount=r["amount"],
            )
            for r in item_rows
        ]
        return WeeklyPlan(
            id=row["id"],
            timestamp=date.fromisoformat(row["timestamp"]),
            recipe_ids=json.loads(row["recipe_ids"]),
            shopping_items=shopping_items,
            created_at=datetime.fromisoformat(row["created_at"]),
        )
