from storage import IngredientStore, RecipeStore
from tests.factories import make_recipe, make_ingredient

# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


async def test_recipe_create_no_ingredients(db):
    recipe = make_recipe()
    recipe.ingredients = []
    store = RecipeStore(db)
    recipe_id = await store.create(recipe)
    result = await store.get(recipe_id)
    assert result.ingredients == []


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


async def test_recipe_create_and_get(db):
    store = RecipeStore(db)
    recipe = make_recipe()
    recipe_id = await store.create(recipe)
    result = await store.get(recipe_id)
    assert result.name == "Pasta"
    assert len(result.ingredients) == 2
    assert result.ingredients[0].name == "Pasta"


async def test_recipe_get_nonexistent_returns_none(db):
    assert await RecipeStore(db).get(999) is None


# ---------------------------------------------------------------------------
# get_by_ids
# ---------------------------------------------------------------------------


async def test_recipe_get_by_ids(db):
    store = RecipeStore(db)
    id1 = await store.create(make_recipe(name="Pasta"))
    await store.create(make_recipe(name="Salad"))
    id3 = await store.create(make_recipe(name="Cake"))
    results = await store.get_by_ids([id1, id3])
    assert len(results) == 2
    names = {r.name for r in results}
    assert names == {"Pasta", "Cake"}


async def test_get_by_ids_empty_list_returns_empty(db):
    store = RecipeStore(db)
    result = await store.get_by_ids([])
    assert result == []


# ---------------------------------------------------------------------------
# get_all_unembedded
# ---------------------------------------------------------------------------


async def test_get_all_unembedded_empty_db(db):
    assert await RecipeStore(db).get_all_unembedded() == []


async def test_get_all_unembedded_returns_new_recipes(db):
    store = RecipeStore(db)
    await store.create(make_recipe())
    result = await store.get_all_unembedded()
    assert len(result) == 1


async def test_get_all_unembedded_excludes_embedded_recipes(db):
    store = RecipeStore(db)
    id1 = await store.create(make_recipe())
    id2 = await store.create(make_recipe())
    await store.update_embedded([id1])
    unembedded = await store.get_all_unembedded()
    assert len(unembedded) == 1
    assert unembedded[0].id == id2


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


async def test_recipe_update(db):
    store = RecipeStore(db)
    recipe_id = await store.create(make_recipe())
    recipe = await store.get(recipe_id)
    assert recipe.name == "Pasta"
    assert recipe.ingredients[0].name == "Pasta"
    assert recipe.ingredients[0].unit == "g"
    assert recipe.ingredients[0].amount == 200.0

    recipe.name = "Spaghetti"
    recipe.ingredients = [make_ingredient(name="Spaghetti", unit="g", amount=300)]
    await store.update(recipe)
    updated = await store.get(recipe_id)
    assert updated.name == "Spaghetti"
    assert len(updated.ingredients) == 1
    assert updated.ingredients[0].name == "Spaghetti"
    assert updated.ingredients[0].unit == "g"
    assert updated.ingredients[0].amount == 300.0


async def test_recipe_update_clears_ingredients(db):
    store = RecipeStore(db)
    recipe_id = await store.create(make_recipe())
    recipe = await store.get(recipe_id)
    assert len(recipe.ingredients) > 0

    recipe.ingredients = []
    await store.update(recipe)
    result = await store.get(recipe_id)
    assert result.ingredients == []


# ---------------------------------------------------------------------------
# update_embedded
# ---------------------------------------------------------------------------


async def test_update_embedded_single(db):
    store = RecipeStore(db)
    recipe_id = await store.create(make_recipe())
    await store.update_embedded([recipe_id])
    assert await store.get_all_unembedded() == []


async def test_update_embedded_multiple(db):
    store = RecipeStore(db)
    id1 = await store.create(make_recipe(name="A"))
    id2 = await store.create(make_recipe(name="B"))
    id3 = await store.create(make_recipe(name="C"))

    await store.update_embedded([id1, id2, id3])
    r1 = await store.get(id1)
    assert r1.embedded
    r2 = await store.get(id2)
    assert r2.embedded
    r3 = await store.get(id3)
    assert r3.embedded
    assert await store.get_all_unembedded() == []


async def test_update_embedded_empty_list_is_noop(db):
    store = RecipeStore(db)
    await store.create(make_recipe())
    await store.update_embedded([])
    assert len(await store.get_all_unembedded()) == 1


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


async def test_recipe_delete_cascades_ingredients(db):
    store = RecipeStore(db)
    ing_store = IngredientStore(db)
    await store.create(make_recipe())
    assert len(await ing_store.get_all()) == 2
    await store.delete(1)
    assert await store.get(1) is None
    assert len(await ing_store.get_all()) == 0


async def test_recipe_delete_nonexistent_no_error(db):
    await RecipeStore(db).delete(999)
