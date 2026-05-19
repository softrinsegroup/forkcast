import json
from datetime import datetime, date
from typing import Protocol

import asyncpg
from models import WeeklyPlan, ShoppingItem
import utils.date


class IWeeklyPlanStore(Protocol):
    async def create(self, plan: WeeklyPlan) -> int: ...
    async def get(self, id: int) -> WeeklyPlan | None: ...
    async def get_last_weekly_plan_recipe_ids(self) -> WeeklyPlan | None: ...
    async def update(self, plan: WeeklyPlan) -> None: ...
    async def delete(self, id: int) -> None: ...


class WeeklyPlanStore:
    def __init__(self, db: asyncpg.connection.Connection):
        self.db = db

    async def create(self, plan: WeeklyPlan) -> int:
        async with self.db.transaction():
            weekly_plan_id = await self.db.fetchval(
                "INSERT INTO weekly_plans (timestamp, recipe_ids, created_at) "
                "VALUES ($1, $2, $3) "
                "RETURNING id",
                plan.timestamp,
                json.dumps(plan.recipe_ids),
                plan.created_at,
            )
            if weekly_plan_id is None:
                raise RuntimeError("INSERT into weekly_plans returned no rowid")

            for item in plan.shopping_items:
                await self.db.execute(
                    "INSERT INTO shopping_items (weekly_plan_id, ingredient_name, unit, amount) "
                    "VALUES ($1, $2, $3, $4)",
                    weekly_plan_id,
                    item.ingredient_name,
                    item.unit,
                    item.amount,
                )

            print(f"WeeklyPlan created: timestamp={plan.timestamp.isoformat()}")

            return weekly_plan_id

    async def get(self, id: int) -> WeeklyPlan | None:
        row = await self.db.fetchrow("SELECT * FROM weekly_plans WHERE id = $1", id)
        if row is None:
            return None
        return await self._parse_weekly_plan(row)

    async def get_last_weekly_plan_recipe_ids(self) -> WeeklyPlan | None:
        last_monday = utils.date.last_monday()

        row = await self.db.fetchrow(
            "SELECT * FROM weekly_plans WHERE timestamp = $1 LIMIT 1",
            last_monday,
        )
        if row is None:
            return None
        return await self._parse_weekly_plan(row)

    async def update(self, plan: WeeklyPlan) -> None:
        async with self.db.transaction():
            await self.db.execute(
                "UPDATE weekly_plans SET timestamp=$1, recipe_ids=$2, created_at=$3 WHERE id=$4",
                plan.timestamp,
                json.dumps(plan.recipe_ids),
                plan.created_at,
                plan.id,
            )

    async def delete(self, id: int) -> None:
        async with self.db.transaction():
            await self.db.execute("DELETE FROM weekly_plans WHERE id = $1", id)

    async def _parse_weekly_plan(self, row) -> WeeklyPlan:
        item_rows = await self.db.fetch(
            "SELECT * FROM shopping_items WHERE weekly_plan_id = $1", row["id"]
        )
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
            timestamp=row["timestamp"],
            recipe_ids=json.loads(row["recipe_ids"]),
            shopping_items=shopping_items,
            created_at=row["created_at"],
        )
