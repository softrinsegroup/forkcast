import json
import asyncpg
import structlog

from models import Ingredient, Recipe

log = structlog.get_logger()


class RecipeStore:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def create(self, recipe: Recipe) -> int:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                recipe_id = await conn.fetchval(
                    "INSERT INTO recipes (name, instructions, servings, prep_minutes, cook_minutes, tags, created_at) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7) "
                    "RETURNING id",
                    recipe.name,
                    json.dumps(recipe.instructions),
                    recipe.servings,
                    recipe.prep_minutes,
                    recipe.cook_minutes,
                    json.dumps(recipe.tags),
                    recipe.created_at,
                )
                if recipe_id is None:
                    raise RuntimeError("INSERT into recipes returned no rowid")

                for ingredient in recipe.ingredients:
                    await conn.execute(
                        "INSERT INTO ingredients (recipe_id, name, unit, amount) "
                        "VALUES ($1, $2, $3, $4)",
                        recipe_id,
                        ingredient.name,
                        ingredient.unit,
                        ingredient.amount,
                    )

                log.info("recipe_created", recipe_id=recipe_id, name=recipe.name)

                return recipe_id

    async def get(self, id: int) -> Recipe | None:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM recipes WHERE id = $1", id)
            if row is None:
                return None
            return await self._load_recipe(conn, dict(row))

    async def get_by_ids(self, ids: list[int]) -> list[Recipe]:
        if not ids:
            return []

        placeholders = ", ".join(f"${i + 1}" for i in range(len(ids)))
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM recipes WHERE id IN ({placeholders})", *ids
            )
            # TODO: N+1 query, ok for now, refactor later
            return [await self._load_recipe(conn, dict(r)) for r in rows]

    async def get_all_unembedded(self) -> list[Recipe]:
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM recipes WHERE embedded = false")
            # TODO: N+1 query, ok for now, refactor later
            return [await self._load_recipe(conn, dict(row)) for row in rows]

    async def update(self, recipe: Recipe) -> None:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE recipes SET name=$1, instructions=$2, servings=$3, prep_minutes=$4, "
                    "cook_minutes=$5, tags=$6, created_at=$7 WHERE id=$8",
                    recipe.name,
                    json.dumps(recipe.instructions),
                    recipe.servings,
                    recipe.prep_minutes,
                    recipe.cook_minutes,
                    json.dumps(recipe.tags),
                    recipe.created_at,
                    recipe.id,
                )
                await conn.execute(
                    "DELETE FROM ingredients WHERE recipe_id = $1", recipe.id
                )
                for ingredient in recipe.ingredients:
                    await conn.execute(
                        "INSERT INTO ingredients (recipe_id, name, unit, amount) "
                        "VALUES ($1, $2, $3, $4)",
                        recipe.id,
                        ingredient.name,
                        ingredient.unit,
                        ingredient.amount,
                    )

    async def update_embedded(self, recipe_ids: list[int]) -> None:
        if not recipe_ids:
            return

        placeholders = ",".join(f"${i + 1}" for i in range(len(recipe_ids)))
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    f"UPDATE recipes SET embedded=true WHERE id IN ({placeholders})",
                    *recipe_ids,
                )

    async def delete(self, id: int) -> None:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM recipes WHERE id = $1", id)

    async def _load_recipe(self, conn: asyncpg.Connection, row: dict) -> Recipe:
        ing_rows = await conn.fetch(
            "SELECT * FROM ingredients WHERE recipe_id = $1", row["id"]
        )
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
            created_at=row["created_at"],
            embedded=row["embedded"],
        )
