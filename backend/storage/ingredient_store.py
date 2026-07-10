import asyncpg
import structlog

from models import Ingredient, IngredientCreate

log = structlog.get_logger()


class IngredientStore:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def create(self, data: IngredientCreate) -> int:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                ingredient_id = await conn.fetchval(
                    "INSERT INTO ingredients (recipe_id, name, unit, amount) "
                    "VALUES ($1, $2, $3, $4) "
                    "RETURNING id",
                    data.recipe_id,
                    data.name,
                    data.unit,
                    data.amount,
                )
                if ingredient_id is None:
                    raise RuntimeError("INSERT into ingredients returned no rowid")

                log.info(
                    "ingredient_created",
                    ingredient_id=ingredient_id,
                    recipe_id=data.recipe_id,
                    name=data.name,
                )

                return ingredient_id

    async def get(self, id: int) -> Ingredient | None:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM ingredients WHERE id = $1", id)
            return self._load(dict(row)) if row is not None else None

    async def get_all(self) -> list[Ingredient]:
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM ingredients")
            return [self._load(dict(r)) for r in rows]

    async def update(self, ingredient: Ingredient) -> None:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE ingredients SET name=$1, unit=$2, amount=$3 WHERE id=$4",
                    ingredient.name,
                    ingredient.unit,
                    ingredient.amount,
                    ingredient.id,
                )

    async def delete(self, id: int) -> None:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM ingredients WHERE id = $1", id)

    def _load(self, row: dict) -> Ingredient:
        return Ingredient(
            id=row["id"], name=row["name"], unit=row["unit"], amount=row["amount"]
        )
