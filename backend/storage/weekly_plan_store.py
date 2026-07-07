import json
from uuid import UUID
import asyncpg
import structlog

from models import WeeklyPlan, ShoppingItem

log = structlog.get_logger()


class WeeklyPlanStore:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def create(self, plan: WeeklyPlan) -> int:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                weekly_plan_id = await conn.fetchval(
                    "INSERT INTO weekly_plans (user_id, timestamp, recipe_ids, created_at) "
                    "VALUES ($1, $2, $3, $4) "
                    "RETURNING id",
                    plan.user_id,
                    plan.timestamp,
                    json.dumps(plan.recipe_ids),
                    plan.created_at,
                )
                if weekly_plan_id is None:
                    raise RuntimeError("INSERT into weekly_plans returned no rowid")

                for item in plan.shopping_items:
                    await conn.execute(
                        "INSERT INTO shopping_items (weekly_plan_id, ingredient_name, unit, amount) "
                        "VALUES ($1, $2, $3, $4)",
                        weekly_plan_id,
                        item.ingredient_name,
                        item.unit,
                        item.amount,
                    )

                log.info(
                    "weekly_plan_created",
                    weekly_plan_id=weekly_plan_id,
                    timestamp=plan.timestamp.isoformat(),
                )

                return weekly_plan_id

    async def get(self, id: int) -> WeeklyPlan | None:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM weekly_plans WHERE id = $1", id)
            if row is None:
                return None
            return await self._parse_weekly_plan(conn, dict(row))

    async def get_last_weekly_plan_recipe_ids(self, user_id: str) -> WeeklyPlan | None:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM weekly_plans WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1",
                UUID(user_id),
            )
            if row is None:
                return None
            return await self._parse_weekly_plan(conn, dict(row))

    async def update(self, plan: WeeklyPlan) -> None:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE weekly_plans SET timestamp=$1, recipe_ids=$2, created_at=$3 WHERE id=$4",
                    plan.timestamp,
                    json.dumps(plan.recipe_ids),
                    plan.created_at,
                    plan.id,
                )

    async def delete(self, id: int) -> None:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM weekly_plans WHERE id = $1", id)

    async def _parse_weekly_plan(
        self, conn: asyncpg.Connection, row: dict
    ) -> WeeklyPlan:
        item_rows = await conn.fetch(
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
            user_id=row["user_id"],
            timestamp=row["timestamp"],
            recipe_ids=json.loads(row["recipe_ids"]),
            shopping_items=shopping_items,
            created_at=row["created_at"],
        )
