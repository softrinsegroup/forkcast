from storage import WeeklyPlanStore, ShoppingItemStore
from tests.factories import make_weekly_plan, make_shopping_item


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


async def test_shopping_item_create_and_get(db):
    plan_store = WeeklyPlanStore(db)
    weekly_plan_id = await plan_store.create(make_weekly_plan(shopping_items=[]))

    item_store = ShoppingItemStore(db)
    item_id = await item_store.create(
        make_shopping_item(
            weekly_plan_id=weekly_plan_id,
            ingredient_name="Pasta",
            unit="g",
            amount=200.0,
        )
    )
    item = await item_store.get(item_id)
    assert item.weekly_plan_id == weekly_plan_id
    assert item.ingredient_name == "Pasta"
    assert item.unit == "g"
    assert item.amount == 200.0


async def test_shopping_item_get_nonexistent_returns_none(db):
    assert await ShoppingItemStore(db).get(999) is None


# ---------------------------------------------------------------------------
# get_by_weekly_plan
# ---------------------------------------------------------------------------


async def test_shopping_item_get_by_weekly_plan(db):
    plan_store = WeeklyPlanStore(db)
    weekly_plan_id = await plan_store.create(
        make_weekly_plan(
            shopping_items=[
                make_shopping_item(ingredient_name="Spaghetti"),
                make_shopping_item(ingredient_name="Meatballs"),
            ]
        )
    )

    item_store = ShoppingItemStore(db)
    items = await item_store.get_by_weekly_plan(weekly_plan_id)
    assert len(items) == 2
    assert items[0].weekly_plan_id == weekly_plan_id
    assert items[0].ingredient_name == "Spaghetti"
    assert items[1].weekly_plan_id == weekly_plan_id
    assert items[1].ingredient_name == "Meatballs"


async def test_shopping_item_get_by_weekly_plan_no_items(db):
    weekly_plan_id = await WeeklyPlanStore(db).create(
        make_weekly_plan(shopping_items=[])
    )
    assert await ShoppingItemStore(db).get_by_weekly_plan(weekly_plan_id) == []


async def test_shopping_item_get_by_weekly_plan_nonexistent_plan(db):
    assert await ShoppingItemStore(db).get_by_weekly_plan(999) == []


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


async def test_shopping_item_update(db):
    plan_store = WeeklyPlanStore(db)
    weekly_plan_id = await plan_store.create(
        make_weekly_plan(
            shopping_items=[
                make_shopping_item(ingredient_name="Spaghetti"),
                make_shopping_item(ingredient_name="Meatballs"),
            ]
        )
    )

    item_store = ShoppingItemStore(db)
    items = await item_store.get_by_weekly_plan(weekly_plan_id)
    item = items[1]
    item.amount = 999
    await item_store.update(item.id, item)
    updated = await item_store.get(item.id)
    assert updated.amount == 999


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


async def test_shopping_item_delete(db):
    weekly_plan_id = await WeeklyPlanStore(db).create(make_weekly_plan())

    item_store = ShoppingItemStore(db)
    items = await item_store.get_by_weekly_plan(weekly_plan_id)
    assert len(items) > 0
    for i in items:
        await item_store.delete(i.id)
        assert await item_store.get(i.id) is None


async def test_shopping_item_cascade_delete_via_plan(db):
    plan_store = WeeklyPlanStore(db)
    weekly_plan_id = await plan_store.create(make_weekly_plan())

    item_store = ShoppingItemStore(db)
    items = await item_store.get_by_weekly_plan(weekly_plan_id)
    assert len(items) > 0
    await plan_store.delete(weekly_plan_id)
    deleted = await item_store.get_by_weekly_plan(weekly_plan_id)
    assert len(deleted) == 0


async def test_shopping_item_delete_nonexistent_no_error(db):
    await ShoppingItemStore(db).delete(999)
