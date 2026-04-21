# Tasks: Storage Layer

## Dependencies

- [x] Add `yoyo-migrations` as a project dependency via `uv add yoyo-migrations`

## Migrations

- [x] Create `migrations/001_initial_schema.sql` with DDL for `recipes`, `ingredients`, `weekly_plans`, and `shopping_items` tables
- [x] Update `storage/db.py` to add `apply_migrations()` and call it synchronously inside `init_db()` before opening the async connection

## Recipe Store

- [x] Create `storage/recipe_store.py` with `IRecipeStore` Protocol
- [x] Implement `RecipeStore.create()` — insert recipe row and all ingredient rows in one transaction
- [x] Implement `RecipeStore.get()` — JOIN with `ingredients`, reconstruct `list[Ingredient]`
- [x] Implement `RecipeStore.get_all()` — JOIN with `ingredients`, group by recipe id
- [x] Implement `RecipeStore.update()` — delete existing ingredient rows, re-insert from updated model
- [x] Implement `RecipeStore.delete()` — delete recipe row (cascades to ingredients)

## Ingredient Store

- [x] Create `storage/ingredient_store.py` with `IIngredientStore` Protocol
- [x] Implement `IngredientStore.create()`
- [x] Implement `IngredientStore.get()`
- [x] Implement `IngredientStore.get_all()`
- [x] Implement `IngredientStore.update()`
- [x] Implement `IngredientStore.delete()`

## Weekly Plan Store

- [x] Create `storage/weekly_plan_store.py` with `IWeeklyPlanStore` Protocol
- [x] Implement `WeeklyPlanStore.create()`
- [x] Implement `WeeklyPlanStore.get()` — keyed by `id: int`
- [x] Implement `WeeklyPlanStore.get_all()`
- [x] Implement `WeeklyPlanStore.update()`
- [x] Implement `WeeklyPlanStore.delete()` — keyed by `id: int`

## Shopping Item Store

- [x] Create `storage/shopping_item_store.py` with `IShoppingItemStore` Protocol
- [x] Implement `ShoppingItemStore.create()`
- [x] Implement `ShoppingItemStore.get()` — keyed by `id`
- [x] Implement `ShoppingItemStore.get_all()`
- [x] Implement `ShoppingItemStore.get_by_weekly_plan()` — keyed by `weekly_plan_id`
- [x] Implement `ShoppingItemStore.update()` — keyed by `id`
- [x] Implement `ShoppingItemStore.delete()` — keyed by `id`

## Exports

- [x] Export all store classes and interfaces from `storage/__init__.py`

## Verification

- [x] Run `uv run pytest` and confirm all tests pass
