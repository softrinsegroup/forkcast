from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.vectorstores import VectorStore
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from storage import init_db, close_db, RecipeStore, WeeklyPlanStore, ShoppingItemStore
from models import Recipe, WeeklyPlan, ShoppingItem, WeeklyPlanCreate
from agent import MealPlanWorkflow, MealPlanInput
from tests.factories import make_ingredient, make_recipe, TEST_USER_ID
import utils.date

# get_last_weekly_plan_recipe_ids() takes a str and wraps it in UUID(), so the
# workflow's user_id must be a str.
USER_ID = str(TEST_USER_ID)


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


def make_mock_vector_store(recipe_ids: list[int]) -> MagicMock:
    vs = MagicMock(spec=VectorStore)
    vs.asimilarity_search = AsyncMock(
        return_value=[
            Document(page_content="", metadata={"recipe_id": rid}) for rid in recipe_ids
        ]
    )
    return vs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db():
    conn = await init_db()
    await conn.execute(
        "TRUNCATE users, recipes, weekly_plans, shopping_items, ingredients RESTART IDENTITY CASCADE"
    )
    await conn.execute(
        "INSERT INTO users (id, email, google_sub) VALUES ($1, $2, $3)",
        TEST_USER_ID,
        "test@example.com",
        "test-google-sub",
    )
    yield conn
    await close_db(conn)


@pytest.fixture
async def workflow(db, mock_prompt_store):
    model = make_mock_model([1, 2, 3, 4, 5])
    return MealPlanWorkflow(
        USER_ID,
        model,
        RecipeStore(db),
        WeeklyPlanStore(db),
        ShoppingItemStore(db),
        mock_prompt_store,
        make_mock_vector_store([1, 2, 3, 4, 5]),
    )


# ---------------------------------------------------------------------------
# _build_recipe_bank
# ---------------------------------------------------------------------------


async def test_fetch_recipe_bank_empty(workflow):
    await workflow._build_recipe_bank("")
    assert workflow.recipe_bank == {}


async def test_fetch_recipe_bank_populated(db, mock_prompt_store):
    recipe_store = RecipeStore(db)
    for i in range(1, 6):
        await recipe_store.create(make_recipe(name=f"Recipe {i}"))

    wf = MealPlanWorkflow(
        USER_ID,
        make_mock_model([1, 2, 3, 4, 5]),
        recipe_store,
        WeeklyPlanStore(db),
        ShoppingItemStore(db),
        mock_prompt_store,
        make_mock_vector_store([1, 2, 3, 4, 5]),
    )
    await wf._build_recipe_bank("")

    assert len(wf.recipe_bank) == 5
    assert all(isinstance(r, Recipe) for r in wf.recipe_bank.values())


async def test_fetch_recipe_bank_keys_are_ids(db, mock_prompt_store):
    recipe_store = RecipeStore(db)
    id = await recipe_store.create(make_recipe(name="Soup"))

    wf = MealPlanWorkflow(
        USER_ID,
        make_mock_model([id]),
        recipe_store,
        WeeklyPlanStore(db),
        ShoppingItemStore(db),
        mock_prompt_store,
        make_mock_vector_store([id]),
    )
    await wf._build_recipe_bank("")

    assert id in wf.recipe_bank
    assert wf.recipe_bank[id].name == "Soup"


# ---------------------------------------------------------------------------
# _fetch_prev_recipe_ids
# ---------------------------------------------------------------------------


async def test_fetch_prev_recipe_ids_none(workflow):
    await workflow._fetch_prev_recipe_ids()
    assert workflow.prev_recipe_ids == []


async def test_fetch_prev_recipe_ids_existing_plan(db, mock_prompt_store):
    plan_store = WeeklyPlanStore(db)
    data = WeeklyPlanCreate(
        user_id=TEST_USER_ID,
        timestamp=utils.date.last_monday(),
        recipe_ids=[10, 20, 30],
        shopping_items=[],
    )
    await plan_store.create(data)

    wf = MealPlanWorkflow(
        USER_ID,
        make_mock_model([1]),
        RecipeStore(db),
        plan_store,
        ShoppingItemStore(db),
        mock_prompt_store,
        make_mock_vector_store([]),
    )
    await wf._fetch_prev_recipe_ids()

    assert wf.prev_recipe_ids == [10, 20, 30]


# ---------------------------------------------------------------------------
# _get_recommended_recipes
# ---------------------------------------------------------------------------


async def test_get_recommended_sets_new_recipe_ids(db, mock_prompt_store):
    recipe_store = RecipeStore(db)
    for i in range(1, 6):
        await recipe_store.create(make_recipe())

    model = make_mock_model([1, 2, 3, 4, 5])
    wf = MealPlanWorkflow(
        USER_ID,
        model,
        recipe_store,
        WeeklyPlanStore(db),
        ShoppingItemStore(db),
        mock_prompt_store,
        make_mock_vector_store([1, 2, 3, 4, 5]),
    )
    await wf._build_recipe_bank("")
    await wf._get_recommended_recipes()

    assert wf.new_recipe_ids == [1, 2, 3, 4, 5]


async def test_get_recommended_raises_on_unknown_recipe_id(db, mock_prompt_store):
    recipe_store = RecipeStore(db)
    for i in range(1, 6):
        await recipe_store.create(make_recipe())

    model = make_mock_model([1, 2, 3, 4, 999])
    wf = MealPlanWorkflow(
        USER_ID,
        model,
        recipe_store,
        WeeklyPlanStore(db),
        ShoppingItemStore(db),
        mock_prompt_store,
        make_mock_vector_store([1, 2, 3, 4, 5]),
    )
    await wf._build_recipe_bank("")

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


async def test_persist_aggregates_shared_ingredients(db, mock_prompt_store):
    r1 = make_recipe(
        ingredients=[make_ingredient(id=1, name="Chicken", unit="g", amount=100.0)]
    )
    r2 = make_recipe(
        ingredients=[make_ingredient(id=2, name="Chicken", unit="g", amount=150.0)]
    )
    recipe_store = RecipeStore(db)
    await recipe_store.create(r1)
    await recipe_store.create(r2)

    wf = MealPlanWorkflow(
        USER_ID,
        make_mock_model([1, 2]),
        recipe_store,
        WeeklyPlanStore(db),
        ShoppingItemStore(db),
        mock_prompt_store,
        make_mock_vector_store([1, 2]),
    )
    await wf._build_recipe_bank("")
    wf.new_recipe_ids = [1, 2]
    await wf._persist_weekly_plan()

    chicken_items = [
        si for si in wf.new_shopping_items if si.ingredient_name == "Chicken"
    ]
    assert len(chicken_items) == 1
    assert chicken_items[0].amount == 250.0


async def test_persist_creates_one_shopping_item_per_unique_ingredient(
    db, mock_prompt_store
):
    r1 = make_recipe(
        ingredients=[
            make_ingredient(id=1, name="Chicken", unit="g", amount=100.0),
            make_ingredient(id=2, name="Rice", unit="g", amount=150.0),
        ],
    )
    r2 = make_recipe(
        ingredients=[
            make_ingredient(id=3, name="Broccoli", unit="g", amount=80.0),
            make_ingredient(id=4, name="Garlic", unit="clove", amount=2.0),
        ],
    )
    recipe_store = RecipeStore(db)
    await recipe_store.create(r1)
    await recipe_store.create(r2)

    wf = MealPlanWorkflow(
        USER_ID,
        make_mock_model([1, 2]),
        recipe_store,
        WeeklyPlanStore(db),
        ShoppingItemStore(db),
        mock_prompt_store,
        make_mock_vector_store([1, 2]),
    )
    await wf._build_recipe_bank("")
    wf.new_recipe_ids = [1, 2]
    await wf._persist_weekly_plan()

    assert len(wf.new_shopping_items) == 4


# ---------------------------------------------------------------------------
# _format_message
# ---------------------------------------------------------------------------


async def test_format_message_contains_week_header(workflow):
    workflow.recipe_bank = {1: make_recipe(id=1, name="Pasta", tags=["italian"])}
    workflow.new_recipe_ids = [1]
    workflow.new_weekly_plan = WeeklyPlan(
        id=1,
        user_id=TEST_USER_ID,
        timestamp=utils.date.this_monday(),
        recipe_ids=[1],
        shopping_items=[],
        created_at=datetime(2026, 4, 20, 12, 0, 0),
    )
    workflow.new_shopping_items = []

    msg = workflow._format_message()
    recipes_msg = msg[0]

    assert "**Week of " in recipes_msg
    assert utils.date.this_monday().isoformat() in recipes_msg


async def test_format_message_lists_recipes_with_tags(workflow):
    workflow.recipe_bank = {
        1: make_recipe(id=1, name="Pasta", tags=["italian", "easy"]),
        2: make_recipe(id=2, name="Salad", tags=["healthy"]),
    }
    workflow.new_recipe_ids = [1, 2]
    workflow.new_weekly_plan = WeeklyPlan(
        id=1,
        user_id=TEST_USER_ID,
        timestamp=utils.date.this_monday(),
        recipe_ids=[1, 2],
        shopping_items=[],
        created_at=datetime(2026, 4, 20, 12, 0, 0),
    )
    workflow.new_shopping_items = []

    msg = workflow._format_message()
    tags_msg = msg[0]

    assert "Pasta" in tags_msg
    assert "italian" in tags_msg
    assert "Salad" in tags_msg
    assert "healthy" in tags_msg


async def test_format_message_lists_shopping_items(workflow):
    workflow.recipe_bank = {1: make_recipe()}
    workflow.new_recipe_ids = [1]
    workflow.new_weekly_plan = WeeklyPlan(
        id=1,
        user_id=TEST_USER_ID,
        timestamp=utils.date.this_monday(),
        recipe_ids=[1],
        shopping_items=[],
        created_at=datetime(2026, 4, 20, 12, 0, 0),
    )
    workflow.new_shopping_items = [
        ShoppingItem(
            id=1, weekly_plan_id=1, ingredient_name="Chicken", unit="g", amount=200.0
        )
    ]

    msg = workflow._format_message()
    shopping_msg = msg[2]

    assert "**Shopping List**" in shopping_msg
    assert "Chicken" in shopping_msg
    assert "200.0" in shopping_msg


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


async def test_run_returns_nonempty_str(db, mock_prompt_store):
    recipe_store = RecipeStore(db)
    for i in range(1, 6):
        await recipe_store.create(make_recipe())

    model = make_mock_model([1, 2, 3, 4, 5])
    wf = MealPlanWorkflow(
        USER_ID,
        model,
        recipe_store,
        WeeklyPlanStore(db),
        ShoppingItemStore(db),
        mock_prompt_store,
        make_mock_vector_store([1, 2, 3, 4, 5]),
    )
    msgs = await wf.run("")
    assert "Week of" in msgs[0]
    assert "Notes" in msgs[1]
    assert "Shopping List" in msgs[2]


async def test_run_persists_weekly_plan_and_items(db, mock_prompt_store):
    recipe_store = RecipeStore(db)
    for i in range(1, 6):
        await recipe_store.create(
            make_recipe(
                ingredients=[
                    make_ingredient(id=i, name=f"ing{i}", unit="g", amount=100.0)
                ]
            )
        )

    plan_store = WeeklyPlanStore(db)
    item_store = ShoppingItemStore(db)
    model = make_mock_model([1, 2, 3, 4, 5])
    wf = MealPlanWorkflow(
        USER_ID,
        model,
        recipe_store,
        plan_store,
        item_store,
        mock_prompt_store,
        make_mock_vector_store([1, 2, 3, 4, 5]),
    )
    await wf.run("")

    plan = await plan_store.get(1)
    plan.recipe_ids = [1, 2, 3, 4, 5]

    items = await item_store.get_by_weekly_plan(plan.id)
    assert len(items) > 0


async def test_run_with_no_previous_plan(db, mock_prompt_store):
    recipe_store = RecipeStore(db)
    for i in range(1, 6):
        await recipe_store.create(make_recipe())

    model = make_mock_model([1, 2, 3, 4, 5])
    wf = MealPlanWorkflow(
        USER_ID,
        model,
        recipe_store,
        WeeklyPlanStore(db),
        ShoppingItemStore(db),
        mock_prompt_store,
        make_mock_vector_store([1, 2, 3, 4, 5]),
    )
    await wf._build_recipe_bank("")
    await wf._fetch_prev_recipe_ids()

    assert wf.prev_recipe_ids == []

    msgs = await wf.run("")
    assert "Week of" in msgs[0]
    assert "Notes" in msgs[1]
    assert "Shopping List" in msgs[2]
