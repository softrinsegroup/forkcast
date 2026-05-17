from typing import Protocol
import aiosqlite

from models import ShoppingItem
from storage.db import transaction


class IShoppingItemStore(Protocol):
    async def create(self, item: ShoppingItem) -> None: ...
    async def get(self, id: int) -> ShoppingItem | None: ...
    async def get_all(self) -> list[ShoppingItem]: ...
    async def get_by_weekly_plan(self, weekly_plan_id: int) -> list[ShoppingItem]: ...
    async def update(self, id: int, item: ShoppingItem) -> None: ...
    async def delete(self, id: int) -> None: ...


class ShoppingItemStore:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def create(self, item: ShoppingItem) -> int:
        async with transaction(self.db):
            async with self.db.execute(
                "INSERT INTO shopping_items (weekly_plan_id, ingredient_name, unit, amount) "
                "VALUES (?, ?, ?, ?)",
                (
                    item.weekly_plan_id,
                    item.ingredient_name,
                    item.unit,
                    item.amount,
                ),
            ) as cur:
                return cur.lastrowid

    async def get(self, id: int) -> ShoppingItem | None:
        async with self.db.execute(
            "SELECT * FROM shopping_items WHERE id = ?", (id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return self._parse_shopping_item(row)

    async def get_by_weekly_plan(self, weekly_plan_id: int) -> list[ShoppingItem]:
        async with self.db.execute(
            "SELECT * FROM shopping_items WHERE weekly_plan_id = ?", (weekly_plan_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [self._parse_shopping_item(r) for r in rows]

    async def update(self, id: int, item: ShoppingItem) -> None:
        async with transaction(self.db):
            await self.db.execute(
                "UPDATE shopping_items "
                "SET weekly_plan_id=?, ingredient_name=?, unit=?, amount=? "
                "WHERE id=?",
                (item.weekly_plan_id, item.ingredient_name, item.unit, item.amount, id),
            )

    async def delete(self, id: int) -> None:
        async with transaction(self.db):
            await self.db.execute("DELETE FROM shopping_items WHERE id = ?", (id,))

    @staticmethod
    def _parse_shopping_item(row) -> ShoppingItem:
        return ShoppingItem(
            id=row["id"],
            weekly_plan_id=row["weekly_plan_id"],
            ingredient_name=row["ingredient_name"],
            unit=row["unit"],
            amount=row["amount"],
        )
