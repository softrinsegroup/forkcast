from typing import Protocol
from models.domain import ShoppingItem
from storage.db import get_db


class IShoppingItemStore(Protocol):
    async def create(self, item: ShoppingItem) -> None: ...
    async def get(self, id: int) -> ShoppingItem | None: ...
    async def get_all(self) -> list[ShoppingItem]: ...
    async def get_by_weekly_plan(self, weekly_plan_id: int) -> list[ShoppingItem]: ...
    async def update(self, id: int, item: ShoppingItem) -> None: ...
    async def delete(self, id: int) -> None: ...


class ShoppingItemStore:
    async def create(self, item: ShoppingItem) -> None:
        db = get_db()
        await db.execute(
            "INSERT INTO shopping_items (id, weekly_plan_id, ingredient_name, unit, amount) "
            "VALUES (?, ?, ?, ?, ?)",
            (item.id, item.weekly_plan_id, item.ingredient_name, item.unit, item.amount),
        )
        await db.commit()

    async def get(self, id: int) -> ShoppingItem | None:
        db = get_db()
        async with db.execute("SELECT * FROM shopping_items WHERE id = ?", (id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return self._row_to_item(row)

    async def get_all(self) -> list[ShoppingItem]:
        db = get_db()
        async with db.execute("SELECT * FROM shopping_items") as cur:
            rows = await cur.fetchall()
        return [self._row_to_item(row) for row in rows]

    async def get_by_weekly_plan(self, weekly_plan_id: int) -> list[ShoppingItem]:
        db = get_db()
        async with db.execute(
            "SELECT * FROM shopping_items WHERE weekly_plan_id = ?", (weekly_plan_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [self._row_to_item(row) for row in rows]

    async def update(self, id: int, item: ShoppingItem) -> None:
        db = get_db()
        await db.execute(
            "UPDATE shopping_items SET weekly_plan_id=?, ingredient_name=?, unit=?, amount=? WHERE id=?",
            (item.weekly_plan_id, item.ingredient_name, item.unit, item.amount, id),
        )
        await db.commit()

    async def delete(self, id: int) -> None:
        db = get_db()
        await db.execute("DELETE FROM shopping_items WHERE id = ?", (id,))
        await db.commit()

    @staticmethod
    def _row_to_item(row) -> ShoppingItem:
        return ShoppingItem(
            id=row["id"],
            weekly_plan_id=row["weekly_plan_id"],
            ingredient_name=row["ingredient_name"],
            unit=row["unit"],
            amount=row["amount"],
        )
