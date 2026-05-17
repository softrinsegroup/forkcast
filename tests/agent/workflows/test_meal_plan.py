from langchain_core.language_models import BaseChatModel
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from storage import init_db, close_db, RecipeStore, WeeklyPlanStore, ShoppingItemStore
from models import Recipe, WeeklyPlan, ShoppingItem
from agent import MealPlanWorkflow, MealPlanInput
from tests.factories import make_ingredient, make_recipe
import utils.date


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_model(recipe_ids: list[int], notes: str = "test notes") -> AsyncMock:
    model = MagicMock(spec=BaseChatModel)
    chain = MagicMock()
    chain.ainvoke = AsyncMock(
        return_value=MealPlanInput(recipe_ids=recipe_ids, notes=notes)
    )
    model.bind.return_value.with_structured_output.return_value = chain
    return model


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db(tmp_path):
    conn = await init_db(str(tmp_path / "test.db"))
    yield conn
    await close_db(conn)


@pytest.fixture
async def workflow(db):
    model = make_mock_model([1, 2, 3, 4, 5])
    return MealPlanWorkflow(
        model, RecipeStore(db), WeeklyPlanStore(db), ShoppingItemStore(db)
    )


# ---------------------------------------------------------------------------
# _fetch_recipe_bank
# ---------------------------------------------------------------------------


async def test_fetch_recipe_bank_empty(workflow):
    await workflow._fetch_recipe_bank()
    assert workflow.recipe_bank == {}


async def test_fetch_recipe_bank_populated(db):
    recipe_store = RecipeStore(db)
    for i in range(1, 4):
        await recipe_store.create(make_recipe(name=f"Recipe {i}"))

    wf = MealPlanWorkflow(
        make_mock_model([1, 2, 3]),
        recipe_store,
        WeeklyPlanStore(db),
        ShoppingItemStore(db),
    )
    await wf._fetch_recipe_bank()

    assert len(wf.recipe_bank) == 3
    assert all(isinstance(r, Recipe) for r in wf.recipe_bank.values())


async def test_fetch_recipe_bank_keys_are_ids(db):
    recipe_store = RecipeStore(db)
    await recipe_store.create(make_recipe(name="Soup"))

    wf = MealPlanWorkflow(
        make_mock_model([1]), recipe_store, WeeklyPlanStore(db), ShoppingItemStore(db)
    )
    await wf._fetch_recipe_bank()

    assert 1 in wf.recipe_bank
    assert wf.recipe_bank[1].name == "Soup"


# ---------------------------------------------------------------------------
# _fetch_prev_recipe_ids
# ---------------------------------------------------------------------------


async def test_fetch_prev_recipe_ids_none(workflow):
    await workflow._fetch_prev_recipe_ids()
    assert workflow.prev_recipe_ids == []


async def test_fetch_prev_recipe_ids_existing_plan(db):
    plan_store = WeeklyPlanStore(db)
    plan = WeeklyPlan(
        timestamp=utils.date.last_monday(),
        recipe_ids=[10, 20, 30],
        shopping_items=[],
        created_at=datetime(2026, 4, 20, 12, 0, 0),
    )
    await plan_store.create(plan)

    wf = MealPlanWorkflow(
        make_mock_model([1]), RecipeStore(db), plan_store, ShoppingItemStore(db)
    )
    await wf._fetch_prev_recipe_ids()

    assert wf.prev_recipe_ids == [10, 20, 30]


# ---------------------------------------------------------------------------
# _get_recommended_recipes
# ---------------------------------------------------------------------------


async def test_get_recommended_sets_new_recipe_ids(db):
    recipe_store = RecipeStore(db)
    for i in range(1, 6):
        await recipe_store.create(make_recipe())

    model = make_mock_model([1, 2, 3, 4, 5])
    wf = MealPlanWorkflow(
        model, recipe_store, WeeklyPlanStore(db), ShoppingItemStore(db)
    )
    await wf._fetch_recipe_bank()
    await wf._get_recommended_recipes()

    assert wf.new_recipe_ids == [1, 2, 3, 4, 5]


async def test_get_recommended_raises_on_unknown_recipe_id(db):
    recipe_store = RecipeStore(db)
    for i in range(1, 6):
        await recipe_store.create(make_recipe())

    model = make_mock_model([1, 2, 3, 4, 999])
    wf = MealPlanWorkflow(
        model, recipe_store, WeeklyPlanStore(db), ShoppingItemStore(db)
    )
    await wf._fetch_recipe_bank()

    with pytest.raises(ValueError, match="999"):
        await wf._get_recommended_recipes()


# ---------------------------------------------------------------------------
# _persist_weekly_plan
# ---------------------------------------------------------------------------


async def test_persist_weekly_plan_timestamp_is_this_monday(workflow):
    workflow.recipe_bank = {i: make_recipe() for i in range(1, 6)}
    workflow.new_recipe_ids = [1, 2, 3, 4, 5]
    await workflow._persist_weekly_plan()
    assert workflow.new_weekly_plan.timestamp == utils.date.this_monday()


async def test_persist_weekly_plan_recipe_ids_match(workflow):
    workflow.recipe_bank = {i: make_recipe() for i in range(1, 6)}
    workflow.new_recipe_ids = [1, 2, 3, 4, 5]
    await workflow._persist_weekly_plan()
    assert workflow.new_weekly_plan.recipe_ids == [1, 2, 3, 4, 5]


async def test_persist_aggregates_shared_ingredients(db):
    r1 = make_recipe(ingredients=[make_ingredient("Chicken", "g", 100.0)])
    r2 = make_recipe(ingredients=[make_ingredient("Chicken", "g", 150.0)])
    recipe_store = RecipeStore(db)
    await recipe_store.create(r1)
    await recipe_store.create(r2)

    wf = MealPlanWorkflow(
        make_mock_model([1, 2]),
        recipe_store,
        WeeklyPlanStore(db),
        ShoppingItemStore(db),
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
        ingredients=[
            make_ingredient("Chicken", "g", 100.0),
            make_ingredient("Rice", "g", 150.0),
        ],
    )
    r2 = make_recipe(
        ingredients=[
            make_ingredient("Broccoli", "g", 80.0),
            make_ingredient("Garlic", "clove", 2.0),
        ],
    )
    recipe_store = RecipeStore(db)
    await recipe_store.create(r1)
    await recipe_store.create(r2)

    wf = MealPlanWorkflow(
        make_mock_model([1, 2]),
        recipe_store,
        WeeklyPlanStore(db),
        ShoppingItemStore(db),
    )
    await wf._fetch_recipe_bank()
    wf.new_recipe_ids = [1, 2]
    await wf._persist_weekly_plan()

    assert len(wf.new_shopping_items) == 4


# ---------------------------------------------------------------------------
# _format_message
# ---------------------------------------------------------------------------


async def test_format_message_contains_week_header(workflow):
    workflow.recipe_bank = {1: make_recipe("Pasta", ["italian"])}
    workflow.new_recipe_ids = [1]
    workflow.new_weekly_plan = WeeklyPlan(
        timestamp=utils.date.this_monday(),
        recipe_ids=[1],
        shopping_items=[],
        created_at=datetime(2026, 4, 20, 12, 0, 0),
    )
    workflow.new_shopping_items = []

    msg = workflow._format_message()

    assert "**Week of " in msg
    assert utils.date.this_monday().isoformat() in msg


async def test_format_message_lists_recipes_with_tags(workflow):
    workflow.recipe_bank = {
        1: make_recipe("Pasta", ["italian", "easy"]),
        2: make_recipe("Salad", ["healthy"]),
    }
    workflow.new_recipe_ids = [1, 2]
    workflow.new_weekly_plan = WeeklyPlan(
        timestamp=utils.date.this_monday(),
        recipe_ids=[1, 2],
        shopping_items=[],
        created_at=datetime(2026, 4, 20, 12, 0, 0),
    )
    workflow.new_shopping_items = []

    msg = workflow._format_message()

    assert "Pasta" in msg
    assert "italian" in msg
    assert "Salad" in msg
    assert "healthy" in msg


async def test_format_message_lists_shopping_items(workflow):
    workflow.recipe_bank = {1: make_recipe()}
    workflow.new_recipe_ids = [1]
    workflow.new_weekly_plan = WeeklyPlan(
        timestamp=utils.date.this_monday(),
        recipe_ids=[1],
        shopping_items=[],
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
# run
# ---------------------------------------------------------------------------


async def test_run_returns_tuple(db):
    recipe_store = RecipeStore(db)
    for i in range(1, 6):
        await recipe_store.create(make_recipe())

    model = make_mock_model([1, 2, 3, 4, 5])
    wf = MealPlanWorkflow(
        model, recipe_store, WeeklyPlanStore(db), ShoppingItemStore(db)
    )
    result = await wf.run()

    assert len(result) == 2
    assert isinstance(result[0], str)
    assert len(result[0]) > 0
    assert result[1] is None


async def test_run_persists_weekly_plan_and_items(db):
    recipe_store = RecipeStore(db)
    for i in range(1, 6):
        await recipe_store.create(
            make_recipe(ingredients=[make_ingredient(f"ing{i}", "g", 100.0)])
        )

    plan_store = WeeklyPlanStore(db)
    item_store = ShoppingItemStore(db)
    model = make_mock_model([1, 2, 3, 4, 5])
    wf = MealPlanWorkflow(model, recipe_store, plan_store, item_store)
    await wf.run()

    plan = await plan_store.get(1)
    plan.recipe_ids = [1, 2, 3, 4, 5]

    items = await item_store.get_by_weekly_plan(plan.id)
    assert len(items) > 0


async def test_run_with_no_previous_plan(db):
    recipe_store = RecipeStore(db)
    for i in range(1, 6):
        await recipe_store.create(make_recipe())

    model = make_mock_model([1, 2, 3, 4, 5])
    wf = MealPlanWorkflow(
        model, recipe_store, WeeklyPlanStore(db), ShoppingItemStore(db)
    )
    await wf._fetch_recipe_bank()
    await wf._fetch_prev_recipe_ids()

    assert wf.prev_recipe_ids == []

    result = await wf.run()
    assert isinstance(result[0], str)
    assert result[1] is None
