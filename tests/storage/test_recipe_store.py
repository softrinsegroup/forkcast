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
# get_all
# ---------------------------------------------------------------------------


async def test_recipe_get_all(db):
    store = RecipeStore(db)
    await store.create(make_recipe(name="Pasta"))
    await store.create(make_recipe(name="Salad"))
    results = await store.get_all()
    assert len(results) == 2
    names = {r.name for r in results}
    assert names == {"Pasta", "Salad"}


async def test_recipe_get_all_empty(db):
    assert await RecipeStore(db).get_all() == []


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
