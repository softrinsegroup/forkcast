from datetime import date, datetime

from models import Recipe, Ingredient, WeeklyPlan, ShoppingItem


def make_recipe(
    name: str = "Pasta",
    tags: list[str] | None = None,
    ingredients: list[Ingredient] | None = None,
    servings: int = 2,
    prep_minutes: int = 5,
    cook_minutes: int = 10,
) -> Recipe:
    return Recipe(
        name=name,
        instructions=["Boil water", "Cook pasta"],
        ingredients=ingredients
        if ingredients is not None
        else [
            Ingredient(name="Pasta", unit="g", amount=200),
            Ingredient(name="Salt", unit="tsp", amount=1),
        ],
        servings=servings,
        prep_minutes=prep_minutes,
        cook_minutes=cook_minutes,
        tags=tags if tags is not None else ["easy", "italian"],
        created_at=datetime.today(),
    )


def make_ingredient(
    name: str = "Chicken", unit: str = "g", amount: float = 200.0
) -> Ingredient:
    return Ingredient(name=name, unit=unit, amount=amount)


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
