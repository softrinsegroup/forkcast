# Tests: Storage Layer

## Migrations

### Happy Path
- `apply_migrations()` runs against a fresh DB and creates all four tables
- `apply_migrations()` called twice does not raise an error or duplicate tables

---

## RecipeStore

### Happy Path
- `create()` persists a recipe and its ingredients to the DB
- `get()` returns the full recipe with reconstructed `list[Ingredient]`
- `get_all()` returns all recipes, each with their ingredients
- `update()` changes recipe fields and replaces all ingredient rows
- `delete()` removes the recipe row and cascades to delete its ingredients

### Edge Cases
- `get()` with a non-existent id returns `None`
- `get_all()` on an empty table returns `[]`
- `create()` with a recipe that has no ingredients succeeds
- `update()` replacing ingredients with an empty list removes all ingredient rows
- `delete()` with a non-existent id completes without error

---

## IngredientStore

### Happy Path
- `create()` persists an ingredient linked to a recipe
- `get()` returns the correct ingredient by id
- `get_all()` returns all ingredients across all recipes
- `update()` changes ingredient fields
- `delete()` removes the ingredient row

### Edge Cases
- `get()` with a non-existent id returns `None`
- `get_all()` on an empty table returns `[]`
- Deleting a recipe cascades and removes its ingredients (verify via `get_all()`)

---

## WeeklyPlanStore

### Happy Path
- `create()` persists a weekly plan with its `recipe_ids`
- `get()` returns the correct plan by id with deserialized `recipe_ids`
- `get_all()` returns all plans
- `update()` changes plan fields including `recipe_ids`
- `delete()` removes the plan and cascades to delete its shopping items

### Edge Cases
- `get()` with a non-existent id returns `None`
- `get_all()` on an empty table returns `[]`
- `create()` with an empty `recipe_ids` list succeeds
- `delete()` with a non-existent id completes without error

---

## ShoppingItemStore

### Happy Path
- `create()` persists a shopping item linked to a weekly plan
- `get()` returns the correct shopping item by id
- `get_all()` returns all shopping items across all plans
- `get_by_weekly_plan()` returns only items belonging to the given `weekly_plan_id`
- `update()` changes shopping item fields
- `delete()` removes the shopping item row

### Edge Cases
- `get()` with a non-existent id returns `None`
- `get_all()` on an empty table returns `[]`
- `get_by_weekly_plan()` with a valid plan that has no items returns `[]`
- `get_by_weekly_plan()` with a non-existent `weekly_plan_id` returns `[]`
- Deleting a weekly plan cascades and removes its shopping items (verify via `get_by_weekly_plan()`)
- `delete()` with a non-existent id completes without error
