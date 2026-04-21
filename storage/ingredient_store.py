from typing import Protocol
from models.domain import Ingredient
from storage.db import get_db


class IIngredientStore(Protocol):
    async def create(self, ingredient: Ingredient, recipe_id: int) -> None: ...
    async def get(self, id: int) -> Ingredient | None: ...
    async def get_all(self) -> list[Ingredient]: ...
    async def update(self, ingredient: Ingredient) -> None: ...
    async def delete(self, id: int) -> None: ...


class IngredientStore:
    async def create(self, ingredient: Ingredient, recipe_id: int) -> None:
        db = get_db()
        await db.execute(
            "INSERT INTO ingredients (id, recipe_id, name, unit, amount) VALUES (?, ?, ?, ?, ?)",
            (ingredient.id, recipe_id, ingredient.name, ingredient.unit, ingredient.amount),
        )
        await db.commit()

    async def get(self, id: int) -> Ingredient | None:
        db = get_db()
        async with db.execute("SELECT * FROM ingredients WHERE id = ?", (id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return Ingredient(id=row["id"], name=row["name"], unit=row["unit"], amount=row["amount"])

    async def get_all(self) -> list[Ingredient]:
        db = get_db()
        async with db.execute("SELECT * FROM ingredients") as cur:
            rows = await cur.fetchall()
        return [
            Ingredient(id=r["id"], name=r["name"], unit=r["unit"], amount=r["amount"])
            for r in rows
        ]

    async def update(self, ingredient: Ingredient) -> None:
        db = get_db()
        await db.execute(
            "UPDATE ingredients SET name=?, unit=?, amount=? WHERE id=?",
            (ingredient.name, ingredient.unit, ingredient.amount, ingredient.id),
        )
        await db.commit()

    async def delete(self, id: int) -> None:
        db = get_db()
        await db.execute("DELETE FROM ingredients WHERE id = ?", (id,))
        await db.commit()
