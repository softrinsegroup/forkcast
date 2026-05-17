from datetime import date

from storage import WeeklyPlanStore, ShoppingItemStore
from tests.factories import make_plan, make_item


async def test_weekly_plan_create_and_get(db):
    store = WeeklyPlanStore(db)
    await store.create(make_plan())
    result = await store.get(1)
    assert result.recipe_ids == [1, 2, 3]
    assert result.timestamp == date(2026, 4, 20)


async def test_weekly_plan_get_all(db):
    store = WeeklyPlanStore(db)
    await store.create(make_plan(1))
    await store.create(make_plan(2))
    assert len(await store.get_all()) == 2


async def test_weekly_plan_update(db):
    store = WeeklyPlanStore(db)
    await store.create(make_plan())
    plan = await store.get(1)
    plan.recipe_ids = [4, 5, 6]
    await store.update(plan)
    result = await store.get(1)
    assert result.recipe_ids == [4, 5, 6]


async def test_weekly_plan_delete_cascades_shopping_items(db):
    plan_store = WeeklyPlanStore(db)
    item_store = ShoppingItemStore(db)
    await plan_store.create(make_plan())
    await item_store.create(make_item(weekly_plan_id=1))
    await plan_store.delete(1)
    assert await plan_store.get(1) is None
    assert await item_store.get_by_weekly_plan(1) == []


async def test_weekly_plan_get_nonexistent_returns_none(db):
    assert await WeeklyPlanStore(db).get(999) is None


async def test_weekly_plan_get_all_empty(db):
    assert await WeeklyPlanStore(db).get_all() == []


async def test_weekly_plan_create_empty_recipe_ids(db):
    plan = make_plan(recipe_ids=[])
    await WeeklyPlanStore(db).create(plan)
    result = await WeeklyPlanStore(db).get(1)
    assert result.recipe_ids == []


async def test_weekly_plan_delete_nonexistent_no_error(db):
    await WeeklyPlanStore(db).delete(999)
