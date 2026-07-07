from datetime import date

from storage import WeeklyPlanStore, ShoppingItemStore
from tests.factories import make_weekly_plan, make_shopping_item

# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


async def test_weekly_plan_create_empty_recipe_ids(db):
    plan = make_weekly_plan(recipe_ids=[])
    store = WeeklyPlanStore(db)
    weekly_plan_id = await store.create(plan)
    fetched = await store.get(weekly_plan_id)
    assert fetched.recipe_ids == []


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


async def test_weekly_plan_create_and_get(db):
    store = WeeklyPlanStore(db)
    weekly_plan_id = await store.create(make_weekly_plan())
    plan = await store.get(weekly_plan_id)
    assert plan.recipe_ids == [1, 1, 1, 1, 1]
    assert plan.timestamp == date(2026, 4, 20)


async def test_weekly_plan_get_nonexistent_returns_none(db):
    assert await WeeklyPlanStore(db).get(999) is None


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


async def test_weekly_plan_update(db):
    store = WeeklyPlanStore(db)
    weekly_plan_id = await store.create(make_weekly_plan())
    plan = await store.get(weekly_plan_id)
    assert plan.recipe_ids == [1, 1, 1, 1, 1]
    plan.recipe_ids = [2, 2, 2, 2, 2]
    await store.update(plan)
    result = await store.get(weekly_plan_id)
    assert result.recipe_ids == [2, 2, 2, 2, 2]


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


async def test_weekly_plan_delete_cascades_shopping_items(db):
    plan_store = WeeklyPlanStore(db)
    item_store = ShoppingItemStore(db)
    weekly_plan_id = await plan_store.create(make_weekly_plan())
    await item_store.create(make_shopping_item(weekly_plan_id=weekly_plan_id))
    await plan_store.delete(weekly_plan_id)
    assert await plan_store.get(weekly_plan_id) is None
    assert await item_store.get_by_weekly_plan(weekly_plan_id) == []


async def test_weekly_plan_delete_nonexistent_no_error(db):
    await WeeklyPlanStore(db).delete(999)
