from datetime import date, datetime
from uuid import UUID

from models import Recipe, Ingredient, WeeklyPlan, ShoppingItem

# Fixed user id used across tests. The db fixtures seed a matching users row so
# weekly_plans.user_id (NOT NULL FK to users) is satisfiable.
TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def make_recipe(
    id: int = 1,
    name: str = "Pasta",
    tags: list[str] = ["easy", "italian"],
    ingredients: list[Ingredient] = [
        Ingredient(id=1, name="Pasta", unit="g", amount=200),
        Ingredient(id=2, name="Salt", unit="tsp", amount=1),
    ],
    instructions: list[str] = ["Boil water", "Cook pasta"],
    servings: int = 2,
    prep_minutes: int = 5,
    cook_minutes: int = 10,
    embedded: bool = True,
) -> Recipe:
    return Recipe(
        id=id,
        name=name,
        instructions=instructions,
        ingredients=ingredients,
        servings=servings,
        prep_minutes=prep_minutes,
        cook_minutes=cook_minutes,
        tags=tags,
        created_at=datetime.today(),
        embedded=embedded,
    )


def make_ingredient(
    id: int = 1, name: str = "Chicken", unit: str = "g", amount: float = 200.0
) -> Ingredient:
    return Ingredient(id=id, name=name, unit=unit, amount=amount)


def make_weekly_plan(
    id: int = 1,
    user_id: UUID = TEST_USER_ID,
    timestamp: date = date(2026, 4, 20),
    recipe_ids: list[int] = [1, 1, 1, 1, 1],
    shopping_items: list[ShoppingItem] = [
        ShoppingItem(
            id=1, weekly_plan_id=1, ingredient_name="Pasta", unit="g", amount=200
        ),
        ShoppingItem(
            id=2, weekly_plan_id=1, ingredient_name="Salt", unit="tsp", amount=1
        ),
    ],
    created_at: datetime = datetime.today(),
) -> WeeklyPlan:
    return WeeklyPlan(
        id=id,
        user_id=user_id,
        timestamp=timestamp,
        recipe_ids=recipe_ids,
        shopping_items=shopping_items,
        created_at=created_at,
    )


def make_shopping_item(
    id: int = 1,
    weekly_plan_id: int = 1,
    ingredient_name: str = "Pasta",
    unit: str = "g",
    amount: float = 400.0,
) -> ShoppingItem:
    return ShoppingItem(
        id=id,
        weekly_plan_id=weekly_plan_id,
        ingredient_name=ingredient_name,
        unit=unit,
        amount=amount,
    )
