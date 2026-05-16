from datetime import date, datetime
import pytest

from models import Recipe, Ingredient, WeeklyPlan, ShoppingItem
from storage import init_db, close_db


@pytest.fixture
async def db(tmp_path):
    conn = await init_db(str(tmp_path / "test.db"))
    yield conn
    await close_db(conn)


def make_recipe(name: str = "Pasta") -> Recipe:
    return Recipe(
        name=name,
        instructions=["Boil water", "Cook pasta"],
        ingredients=[
            Ingredient(name="Pasta", unit="g", amount=200),
            Ingredient(name="Salt", unit="tsp", amount=1),
        ],
        servings=2,
        prep_minutes=5,
        cook_minutes=10,
        tags=["easy", "italian"],
        created_at=datetime(2026, 4, 20, 12, 0, 0),
    )


def make_plan(id: int = 1, recipe_ids: list[int] | None = None) -> WeeklyPlan:
    return WeeklyPlan(
        id=id,
        timestamp=date(2026, 4, 20),
        recipe_ids=recipe_ids if recipe_ids is not None else [1, 2, 3],
        created_at=datetime(2026, 4, 20, 12, 0, 0),
    )


def make_item(id: int = 1, weekly_plan_id: int = 1) -> ShoppingItem:
    return ShoppingItem(
        id=id,
        weekly_plan_id=weekly_plan_id,
        ingredient_name="Pasta",
        unit="g",
        amount=400,
    )
