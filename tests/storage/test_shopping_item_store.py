from storage import WeeklyPlanStore, ShoppingItemStore
from tests.factories import make_plan, make_item


async def test_shopping_item_create_and_get(db):
    await WeeklyPlanStore(db).create(make_plan())
    store = ShoppingItemStore(db)
    await store.create(make_item())
    result = await store.get(1)
    assert result.ingredient_name == "Pasta"
    assert result.amount == 400


async def test_shopping_item_get_all(db):
    await WeeklyPlanStore(db).create(make_plan(1))
    await WeeklyPlanStore(db).create(make_plan(2))
    store = ShoppingItemStore(db)
    await store.create(make_item(1, weekly_plan_id=1))
    await store.create(make_item(2, weekly_plan_id=2))
    assert len(await store.get_all()) == 2


async def test_shopping_item_get_by_weekly_plan(db):
    await WeeklyPlanStore(db).create(make_plan(1))
    await WeeklyPlanStore(db).create(make_plan(2))
    store = ShoppingItemStore(db)
    await store.create(make_item(1, weekly_plan_id=1))
    await store.create(make_item(2, weekly_plan_id=1))
    await store.create(make_item(3, weekly_plan_id=2))
    results = await store.get_by_weekly_plan(1)
    assert len(results) == 2
    assert all(r.weekly_plan_id == 1 for r in results)


async def test_shopping_item_update(db):
    await WeeklyPlanStore(db).create(make_plan())
    store = ShoppingItemStore(db)
    await store.create(make_item())
    updated = make_item()
    updated.amount = 999
    await store.update(1, updated)
    result = await store.get(1)
    assert result.amount == 999


async def test_shopping_item_delete(db):
    await WeeklyPlanStore(db).create(make_plan())
    store = ShoppingItemStore(db)
    await store.create(make_item())
    await store.delete(1)
    assert await store.get(1) is None


async def test_shopping_item_get_nonexistent_returns_none(db):
    assert await ShoppingItemStore(db).get(999) is None


async def test_shopping_item_get_all_empty(db):
    assert await ShoppingItemStore(db).get_all() == []


async def test_shopping_item_get_by_weekly_plan_no_items(db):
    await WeeklyPlanStore(db).create(make_plan())
    assert await ShoppingItemStore(db).get_by_weekly_plan(1) == []


async def test_shopping_item_get_by_weekly_plan_nonexistent_plan(db):
    assert await ShoppingItemStore(db).get_by_weekly_plan(999) == []


async def test_shopping_item_cascade_delete_via_plan(db):
    await WeeklyPlanStore(db).create(make_plan())
    store = ShoppingItemStore(db)
    await store.create(make_item())
    await WeeklyPlanStore(db).delete(1)
    assert await store.get_by_weekly_plan(1) == []


async def test_shopping_item_delete_nonexistent_no_error(db):
    await ShoppingItemStore(db).delete(999)
