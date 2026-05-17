import json
from datetime import datetime
from typing import Protocol

import aiosqlite
from models import Ingredient, Recipe


class IRecipeStore(Protocol):
    async def create(self, recipe: Recipe) -> None: ...
    async def get(self, id: int) -> Recipe | None: ...
    async def get_all(self) -> list[Recipe]: ...
    async def update(self, recipe: Recipe) -> None: ...
    async def delete(self, id: int) -> None: ...


class RecipeStore:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def create(self, recipe: Recipe) -> int:
        async with self.db.execute("BEGIN"):
            pass
        cursor = await self.db.execute(
            "INSERT INTO recipes (name, instructions, servings, prep_minutes, cook_minutes, tags, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                recipe.name,
                json.dumps(recipe.instructions),
                recipe.servings,
                recipe.prep_minutes,
                recipe.cook_minutes,
                json.dumps(recipe.tags),
                recipe.created_at.isoformat(),
            ),
        )
        recipe_id = cursor.lastrowid
        for ingredient in recipe.ingredients:
            await self.db.execute(
                "INSERT INTO ingredients (recipe_id, name, unit, amount) VALUES (?, ?, ?, ?)",
                (
                    recipe_id,
                    ingredient.name,
                    ingredient.unit,
                    ingredient.amount,
                ),
            )
        await self.db.commit()
        print(f"Recipe created: {recipe.name}")

        return recipe_id

    async def get(self, id: int) -> Recipe | None:
        async with self.db.execute("SELECT * FROM recipes WHERE id = ?", (id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return await self._load_recipe(dict(row))

    async def get_all(self) -> list[Recipe]:
        async with self.db.execute("SELECT * FROM recipes") as cur:
            rows = await cur.fetchall()
        return [await self._load_recipe(dict(row)) for row in rows]

    async def update(self, recipe: Recipe) -> None:
        await self.db.execute(
            "UPDATE recipes SET name=?, instructions=?, servings=?, prep_minutes=?, "
            "cook_minutes=?, tags=?, created_at=? WHERE id=?",
            (
                recipe.name,
                json.dumps(recipe.instructions),
                recipe.servings,
                recipe.prep_minutes,
                recipe.cook_minutes,
                json.dumps(recipe.tags),
                recipe.created_at.isoformat(),
                recipe.id,
            ),
        )
        await self.db.execute(
            "DELETE FROM ingredients WHERE recipe_id = ?", (recipe.id,)
        )
        for ingredient in recipe.ingredients:
            await self.db.execute(
                "INSERT INTO ingredients (id, recipe_id, name, unit, amount) VALUES (?, ?, ?, ?, ?)",
                (
                    ingredient.id,
                    recipe.id,
                    ingredient.name,
                    ingredient.unit,
                    ingredient.amount,
                ),
            )
        await self.db.commit()

    async def delete(self, id: int) -> None:
        await self.db.execute("DELETE FROM recipes WHERE id = ?", (id,))
        await self.db.commit()

    async def _load_recipe(self, row: dict) -> Recipe:
        async with self.db.execute(
            "SELECT * FROM ingredients WHERE recipe_id = ?", (row["id"],)
        ) as cur:
            ing_rows = await cur.fetchall()
        ingredients = [
            Ingredient(id=r["id"], name=r["name"], unit=r["unit"], amount=r["amount"])
            for r in ing_rows
        ]
        return Recipe(
            id=row["id"],
            name=row["name"],
            instructions=json.loads(row["instructions"]),
            ingredients=ingredients,
            servings=row["servings"],
            prep_minutes=row["prep_minutes"],
            cook_minutes=row["cook_minutes"],
            tags=json.loads(row["tags"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
