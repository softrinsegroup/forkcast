import asyncpg
import structlog

from models import ShoppingItem

log = structlog.get_logger()


class ShoppingItemStore:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def create(self, item: ShoppingItem) -> int:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                shopping_item_id = await conn.fetchval(
                    "INSERT INTO shopping_items (weekly_plan_id, ingredient_name, unit, amount) "
                    "VALUES ($1, $2, $3, $4) "
                    "RETURNING id",
                    item.weekly_plan_id,
                    item.ingredient_name,
                    item.unit,
                    item.amount,
                )
                if shopping_item_id is None:
                    raise RuntimeError("INSERT into shopping_items returned no rowid")

                log.info(
                    "shopping_item_created",
                    shopping_item_id=shopping_item_id,
                    weekly_plan_id=item.weekly_plan_id,
                    ingredient_name=item.ingredient_name,
                )

                return shopping_item_id

    async def get(self, id: int) -> ShoppingItem | None:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM shopping_items WHERE id = $1", id)
            if row is None:
                return None
            return self._parse_shopping_item(dict(row))

    async def get_by_weekly_plan(self, weekly_plan_id: int) -> list[ShoppingItem]:
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM shopping_items WHERE weekly_plan_id = $1", weekly_plan_id
            )
            return [self._parse_shopping_item(dict(r)) for r in rows]

    async def update(self, id: int, item: ShoppingItem) -> None:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE shopping_items "
                    "SET weekly_plan_id=$1, ingredient_name=$2, unit=$3, amount=$4 "
                    "WHERE id=$5",
                    item.weekly_plan_id,
                    item.ingredient_name,
                    item.unit,
                    item.amount,
                    id,
                )

    async def delete(self, id: int) -> None:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM shopping_items WHERE id = $1", id)

    def _parse_shopping_item(self, row: dict) -> ShoppingItem:
        return ShoppingItem(
            id=row["id"],
            weekly_plan_id=row["weekly_plan_id"],
            ingredient_name=row["ingredient_name"],
            unit=row["unit"],
            amount=row["amount"],
        )
