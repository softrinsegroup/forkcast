from storage import IngredientStore, RecipeStore
from tests.factories import make_recipe


async def test_ingredient_create_and_get(db):
    recipe_store = RecipeStore(db)
    await recipe_store.create(make_recipe())
    recipe = await recipe_store.get(1)

    ing_store = IngredientStore(db)
    for ing in recipe.ingredients:
        result = await ing_store.get(ing.id)
        assert result.name == ing.name
        assert result.unit == ing.unit
        assert result.amount == ing.amount


async def test_ingredient_get_all(db):
    recipe_store = RecipeStore(db)
    await recipe_store.create(make_recipe())
    await recipe_store.create(make_recipe())

    ing_store = IngredientStore(db)
    all_ings = await ing_store.get_all()
    assert len(all_ings) == 4


async def test_ingredient_update(db):
    recipe_store = RecipeStore(db)
    await recipe_store.create(make_recipe())
    recipe = await recipe_store.get(1)
    ing_1 = recipe.ingredients[0]

    ing_store = IngredientStore(db)
    ing = await ing_store.get(ing_1.id)
    assert ing.amount != 500
    ing.amount = 500
    await ing_store.update(ing)
    result = await ing_store.get(ing_1.id)
    assert result.amount == 500


async def test_ingredient_delete(db):
    await RecipeStore(db).create(make_recipe())
    ing_store = IngredientStore(db)
    assert await ing_store.get(1) is not None

    await ing_store.delete(1)
    assert await ing_store.get(1) is None


async def test_ingredient_get_nonexistent_returns_none(db):
    assert await IngredientStore(db).get(999) is None


async def test_ingredient_get_all_empty(db):
    assert await IngredientStore(db).get_all() == []


async def test_ingredient_cascade_delete_via_recipe(db):
    recipe_store = RecipeStore(db)
    await recipe_store.create(make_recipe())

    ing_store = IngredientStore(db)
    assert len(await ing_store.get_all()) > 0

    await recipe_store.delete(1)
    assert len(await ing_store.get_all()) == 0
