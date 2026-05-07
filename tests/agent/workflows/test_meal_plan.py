import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from storage import init_db, RecipeStore, WeeklyPlanStore, ShoppingItemStore
from models.domain import Ingredient, Recipe, WeeklyPlan, ShoppingItem
from agent import MealPlanWorkflow
import utils.date


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ingredient(
    name: str = "Chicken", unit: str = "g", amount: float = 200.0
) -> Ingredient:
    return Ingredient(name=name, unit=unit, amount=amount)


def make_recipe(
    id: int = 1,
    name: str = "Pasta",
    tags: list[str] | None = None,
    ingredients: list[Ingredient] | None = None,
) -> Recipe:
    return Recipe(
        id=id,
        name=name,
        instructions=["Step 1"],
        ingredients=ingredients
        if ingredients is not None
        else [Ingredient(id=id * 100 + 1, name="Chicken", unit="g", amount=200.0)],
        servings=2,
        prep_minutes=5,
        cook_minutes=10,
        tags=tags if tags is not None else ["easy"],
        created_at=datetime(2026, 4, 20, 12, 0, 0),
    )


def make_mock_client(recipe_ids: list[int], notes: str = "test notes") -> AsyncMock:
    tool_use_block = MagicMock()
    tool_use_block.input = {"recipe_ids": recipe_ids, "notes": notes}
    response = MagicMock()
    response.content = [tool_use_block]
    client = AsyncMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db(tmp_path):
    await init_db(str(tmp_path / "test.db"))


@pytest.fixture
async def workflow(db):
    client = make_mock_client([1, 2, 3, 4, 5])
    return MealPlanWorkflow(
        client, RecipeStore(), WeeklyPlanStore(), ShoppingItemStore()
    )


# ---------------------------------------------------------------------------
# _fetch_recipe_bank
# ---------------------------------------------------------------------------


async def test_fetch_recipe_bank_empty(workflow):
    await workflow._fetch_recipe_bank()
    assert workflow.recipe_bank == {}


async def test_fetch_recipe_bank_populated(db):
    recipe_store = RecipeStore()
    for i in range(1, 4):
        await recipe_store.create(make_recipe(i, name=f"Recipe {i}"))

    wf = MealPlanWorkflow(
        make_mock_client([1, 2, 3]),
        recipe_store,
        WeeklyPlanStore(),
        ShoppingItemStore(),
    )
    await wf._fetch_recipe_bank()

    assert len(wf.recipe_bank) == 3
    assert all(isinstance(r, Recipe) for r in wf.recipe_bank.values())


async def test_fetch_recipe_bank_keys_are_ids(db):
    recipe_store = RecipeStore()
    await recipe_store.create(make_recipe(id=42, name="Soup"))

    wf = MealPlanWorkflow(
        make_mock_client([42]), recipe_store, WeeklyPlanStore(), ShoppingItemStore()
    )
    await wf._fetch_recipe_bank()

    assert 42 in wf.recipe_bank
    assert wf.recipe_bank[42].name == "Soup"


# ---------------------------------------------------------------------------
# _fetch_prev_recipe_ids
# ---------------------------------------------------------------------------


async def test_fetch_prev_recipe_ids_none(workflow):
    await workflow._fetch_prev_recipe_ids()
    assert workflow.prev_recipe_ids == []


async def test_fetch_prev_recipe_ids_existing_plan(db):
    plan_store = WeeklyPlanStore()
    plan = WeeklyPlan(
        timestamp=utils.date.last_monday(),
        recipe_ids=[10, 20, 30],
        created_at=datetime(2026, 4, 20, 12, 0, 0),
    )
    await plan_store.create(plan)

    wf = MealPlanWorkflow(
        make_mock_client([1]), RecipeStore(), plan_store, ShoppingItemStore()
    )
    await wf._fetch_prev_recipe_ids()

    assert wf.prev_recipe_ids == [10, 20, 30]


# ---------------------------------------------------------------------------
# _get_recommended_recipes — API call parameters
# ---------------------------------------------------------------------------


async def test_get_recommended_uses_correct_model(workflow):
    workflow.recipe_bank = {i: make_recipe(i) for i in range(1, 6)}
    await workflow._get_recommended_recipes()
    kwargs = workflow.client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-4-6"


async def test_get_recommended_uses_max_tokens(workflow):
    workflow.recipe_bank = {i: make_recipe(i) for i in range(1, 6)}
    await workflow._get_recommended_recipes()
    kwargs = workflow.client.messages.create.call_args.kwargs
    assert kwargs["max_tokens"] == 512


async def test_get_recommended_forces_tool_choice(workflow):
    workflow.recipe_bank = {i: make_recipe(i) for i in range(1, 6)}
    await workflow._get_recommended_recipes()
    kwargs = workflow.client.messages.create.call_args.kwargs
    assert kwargs["tool_choice"] == {"type": "tool", "name": "create_meal_plan"}


async def test_get_recommended_system_prompt_has_cache_control(workflow):
    workflow.recipe_bank = {i: make_recipe(i) for i in range(1, 6)}
    await workflow._get_recommended_recipes()
    kwargs = workflow.client.messages.create.call_args.kwargs
    system = kwargs["system"]
    assert len(system) == 1
    assert system[0]["cache_control"] == {"type": "ephemeral"}


async def test_get_recommended_message_includes_recipe_bank_and_prev_ids(workflow):
    workflow.recipe_bank = {i: make_recipe(i) for i in range(1, 6)}
    workflow.prev_recipe_ids = [3]
    await workflow._get_recommended_recipes()
    kwargs = workflow.client.messages.create.call_args.kwargs
    user_content = kwargs["messages"][0]["content"]
    assert "Recipe bank:" in user_content
    assert "Previous recipe_ids:" in user_content


# ---------------------------------------------------------------------------
# _get_recommended_recipes — logic
# ---------------------------------------------------------------------------


async def test_get_recommended_sets_new_recipe_ids(db):
    recipe_store = RecipeStore()
    for i in range(1, 6):
        await recipe_store.create(make_recipe(i))

    client = make_mock_client([1, 2, 3, 4, 5])
    wf = MealPlanWorkflow(client, recipe_store, WeeklyPlanStore(), ShoppingItemStore())
    await wf._fetch_recipe_bank()
    await wf._get_recommended_recipes()

    assert wf.new_recipe_ids == [1, 2, 3, 4, 5]


async def test_get_recommended_raises_on_unknown_recipe_id(db):
    recipe_store = RecipeStore()
    for i in range(1, 6):
        await recipe_store.create(make_recipe(i))

    client = make_mock_client([1, 2, 3, 4, 999])
    wf = MealPlanWorkflow(client, recipe_store, WeeklyPlanStore(), ShoppingItemStore())
    await wf._fetch_recipe_bank()

    with pytest.raises(ValueError, match="999"):
        await wf._get_recommended_recipes()


# ---------------------------------------------------------------------------
# _persist_weekly_plan
# ---------------------------------------------------------------------------


async def test_persist_weekly_plan_timestamp_is_this_monday(workflow):
    workflow.recipe_bank = {i: make_recipe(i) for i in range(1, 6)}
    workflow.new_recipe_ids = [1, 2, 3, 4, 5]
    await workflow._persist_weekly_plan()
    assert workflow.new_weekly_plan.timestamp == utils.date.this_monday()


async def test_persist_weekly_plan_recipe_ids_match(workflow):
    workflow.recipe_bank = {i: make_recipe(i) for i in range(1, 6)}
    workflow.new_recipe_ids = [1, 2, 3, 4, 5]
    await workflow._persist_weekly_plan()
    assert workflow.new_weekly_plan.recipe_ids == [1, 2, 3, 4, 5]


async def test_persist_aggregates_shared_ingredients(db):
    r1 = make_recipe(1, ingredients=[make_ingredient("Chicken", "g", 100.0)])
    r2 = make_recipe(2, ingredients=[make_ingredient("Chicken", "g", 150.0)])
    recipe_store = RecipeStore()
    await recipe_store.create(r1)
    await recipe_store.create(r2)

    wf = MealPlanWorkflow(
        make_mock_client([1, 2]), recipe_store, WeeklyPlanStore(), ShoppingItemStore()
    )
    await wf._fetch_recipe_bank()
    wf.new_recipe_ids = [1, 2]
    await wf._persist_weekly_plan()

    chicken_items = [
        si for si in wf.new_shopping_items if si.ingredient_name == "Chicken"
    ]
    assert len(chicken_items) == 1
    assert chicken_items[0].amount == 250.0


async def test_persist_creates_one_shopping_item_per_unique_ingredient(db):
    r1 = make_recipe(
        1,
        ingredients=[
            make_ingredient("Chicken", "g", 100.0),
            make_ingredient("Rice", "g", 150.0),
        ],
    )
    r2 = make_recipe(
        2,
        ingredients=[
            make_ingredient("Broccoli", "g", 80.0),
            make_ingredient("Garlic", "clove", 2.0),
        ],
    )
    recipe_store = RecipeStore()
    await recipe_store.create(r1)
    await recipe_store.create(r2)

    wf = MealPlanWorkflow(
        make_mock_client([1, 2]), recipe_store, WeeklyPlanStore(), ShoppingItemStore()
    )
    await wf._fetch_recipe_bank()
    wf.new_recipe_ids = [1, 2]
    await wf._persist_weekly_plan()

    assert len(wf.new_shopping_items) == 4


# ---------------------------------------------------------------------------
# _format_message
# ---------------------------------------------------------------------------


async def test_format_message_contains_week_header(workflow):
    workflow.recipe_bank = {1: make_recipe(1, "Pasta", ["italian"])}
    workflow.new_recipe_ids = [1]
    workflow.new_weekly_plan = WeeklyPlan(
        timestamp=utils.date.this_monday(),
        recipe_ids=[1],
        created_at=datetime(2026, 4, 20, 12, 0, 0),
    )
    workflow.new_shopping_items = []

    msg = workflow._format_message()

    assert "**Week of " in msg
    assert utils.date.this_monday().isoformat() in msg


async def test_format_message_lists_recipes_with_tags(workflow):
    workflow.recipe_bank = {
        1: make_recipe(1, "Pasta", ["italian", "easy"]),
        2: make_recipe(2, "Salad", ["healthy"]),
    }
    workflow.new_recipe_ids = [1, 2]
    workflow.new_weekly_plan = WeeklyPlan(
        timestamp=utils.date.this_monday(),
        recipe_ids=[1, 2],
        created_at=datetime(2026, 4, 20, 12, 0, 0),
    )
    workflow.new_shopping_items = []

    msg = workflow._format_message()

    assert "Pasta" in msg
    assert "italian" in msg
    assert "Salad" in msg
    assert "healthy" in msg


async def test_format_message_lists_shopping_items(workflow):
    workflow.recipe_bank = {1: make_recipe(1)}
    workflow.new_recipe_ids = [1]
    workflow.new_weekly_plan = WeeklyPlan(
        timestamp=utils.date.this_monday(),
        recipe_ids=[1],
        created_at=datetime(2026, 4, 20, 12, 0, 0),
    )
    workflow.new_shopping_items = [
        ShoppingItem(
            weekly_plan_id=1, ingredient_name="Chicken", unit="g", amount=200.0
        )
    ]

    msg = workflow._format_message()

    assert "**Shopping List**" in msg
    assert "Chicken" in msg
    assert "200.0" in msg


# ---------------------------------------------------------------------------
# run() — integration
# ---------------------------------------------------------------------------


async def test_run_returns_string(db):
    recipe_store = RecipeStore()
    for i in range(1, 6):
        await recipe_store.create(make_recipe(i))

    client = make_mock_client([1, 2, 3, 4, 5])
    wf = MealPlanWorkflow(client, recipe_store, WeeklyPlanStore(), ShoppingItemStore())
    result = await wf.run()

    assert isinstance(result, str)
    assert len(result) > 0


async def test_run_persists_weekly_plan_and_items(db):
    recipe_store = RecipeStore()
    for i in range(1, 6):
        await recipe_store.create(
            make_recipe(i, ingredients=[make_ingredient(f"ing{i}", "g", 100.0)])
        )

    plan_store = WeeklyPlanStore()
    item_store = ShoppingItemStore()
    client = make_mock_client([1, 2, 3, 4, 5])
    wf = MealPlanWorkflow(client, recipe_store, plan_store, item_store)
    await wf.run()

    plans = await plan_store.get_all()
    assert len(plans) == 1

    items = await item_store.get_by_weekly_plan(plans[0].id)
    assert len(items) > 0


async def test_run_with_no_previous_plan(db):
    recipe_store = RecipeStore()
    for i in range(1, 6):
        await recipe_store.create(make_recipe(i))

    client = make_mock_client([1, 2, 3, 4, 5])
    wf = MealPlanWorkflow(client, recipe_store, WeeklyPlanStore(), ShoppingItemStore())
    await wf._fetch_recipe_bank()
    await wf._fetch_prev_recipe_ids()

    assert wf.prev_recipe_ids == []

    result = await wf.run()
    assert isinstance(result, str)
