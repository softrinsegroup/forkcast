from datetime import date, datetime

from models import Recipe, Ingredient, WeeklyPlan, ShoppingItem


def make_recipe(
    name: str = "Pasta",
    tags: list[str] = ["easy", "italian"],
    ingredients: list[Ingredient] = [
        Ingredient(name="Pasta", unit="g", amount=200),
        Ingredient(name="Salt", unit="tsp", amount=1),
    ],
    instructions: list[str] = ["Boil water", "Cook pasta"],
    servings: int = 2,
    prep_minutes: int = 5,
    cook_minutes: int = 10,
) -> Recipe:
    return Recipe(
        name=name,
        instructions=instructions,
        ingredients=ingredients,
        servings=servings,
        prep_minutes=prep_minutes,
        cook_minutes=cook_minutes,
        tags=tags,
        created_at=datetime.today(),
    )


def make_ingredient(
    name: str = "Chicken", unit: str = "g", amount: float = 200.0
) -> Ingredient:
    return Ingredient(name=name, unit=unit, amount=amount)


def make_weekly_plan(
    timestamp: date = date(2026, 4, 20),
    recipe_ids: list[int] = [1, 1, 1, 1, 1],
    shopping_items: list[ShoppingItem] = [
        ShoppingItem(weekly_plan_id=1, ingredient_name="Pasta", unit="g", amount=200),
        ShoppingItem(weekly_plan_id=1, ingredient_name="Salt", unit="tsp", amount=1),
    ],
    created_at: datetime = datetime.today(),
) -> WeeklyPlan:
    return WeeklyPlan(
        timestamp=timestamp,
        recipe_ids=recipe_ids,
        shopping_items=shopping_items,
        created_at=created_at,
    )


def make_shopping_item(
    weekly_plan_id: int = 1,
    ingredient_name: str = "Pasta",
    unit: str = "g",
    amount: float = 400.0,
) -> ShoppingItem:
    return ShoppingItem(
        weekly_plan_id=weekly_plan_id,
        ingredient_name=ingredient_name,
        unit=unit,
        amount=amount,
    )
