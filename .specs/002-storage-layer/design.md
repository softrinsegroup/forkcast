# Design: Storage Layer

## Architecture

One store class per model, each accepting the shared `aiosqlite.Connection` via `get_db()`. Each store is backed by a `Protocol` interface defining the CRUD contract. Schema initialization is added to `init_db()` in `storage/db.py`.

```
storage/
  db.py                    ← call apply_migrations() inside init_db()
  recipe_store.py          ← RecipeStore + IRecipeStore
  ingredient_store.py      ← IngredientStore + IIngredientStore
  weekly_plan_store.py     ← WeeklyPlanStore + IWeeklyPlanStore
  shopping_item_store.py   ← ShoppingItemStore + IShoppingItemStore
migrations/
  001_initial_schema.sql   ← all DDL lives here
```

## SQL Schema

Schema lives in `migrations/001_initial_schema.sql`. Subsequent changes each get a new numbered file (e.g. `002_add_meal_type.sql`). yoyo tracks applied migrations in a `_yoyo_migration` table automatically.

`init_db()` in `storage/db.py` applies all pending migrations synchronously before the async connection is opened:

```python
from yoyo import read_migrations, get_backend

def apply_migrations(db_path: str) -> None:
    backend = get_backend(f"sqlite:///{db_path}")
    migrations = read_migrations("migrations/")
    with backend.lock():
        backend.apply_one(migrations)

async def init_db(path: str) -> None:
    global _db
    if _db is not None:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    apply_migrations(path)          # sync, runs before async connect
    _db = await aiosqlite.connect(path)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
```

The tables (`recipes`, `ingredients`, `weekly_plans`, `shopping_items`) are defined in `migrations/001_initial_schema.sql`. `Ingredient` rows are owned by a `Recipe` — `ON DELETE CASCADE` removes them when the recipe is deleted.

### recipes

```sql
CREATE TABLE IF NOT EXISTS recipes (
    id           INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    instructions TEXT    NOT NULL,  -- JSON array of strings
    servings     INTEGER NOT NULL,
    prep_minutes INTEGER NOT NULL,
    cook_minutes INTEGER NOT NULL,
    tags         TEXT    NOT NULL,  -- JSON array of strings
    created_at   TEXT    NOT NULL   -- ISO-8601
);
```

### ingredients

```sql
CREATE TABLE IF NOT EXISTS ingredients (
    id        INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    name      TEXT    NOT NULL,
    unit      TEXT    NOT NULL,
    amount    REAL    NOT NULL
);
```

### weekly_plans

```sql
CREATE TABLE IF NOT EXISTS weekly_plans (
    id         INTEGER PRIMARY KEY,
    timestamp  TEXT NOT NULL,      -- ISO date e.g. "2026-04-20"
    recipe_ids TEXT NOT NULL,      -- JSON array of ints
    created_at TEXT NOT NULL
);
```

### shopping_items

```sql
CREATE TABLE IF NOT EXISTS shopping_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    weekly_plan_id  INTEGER NOT NULL REFERENCES weekly_plans(id) ON DELETE CASCADE,
    ingredient_name TEXT    NOT NULL,
    unit            TEXT    NOT NULL,
    amount          REAL    NOT NULL
);
```

## Interfaces

Each store exposes a `Protocol` so callers depend on the interface, not the implementation:

```python
class IRecipeStore(Protocol):
    async def create(self, recipe: Recipe) -> None: ...
    async def get(self, id: int) -> Recipe | None: ...
    async def get_all(self) -> list[Recipe]: ...
    async def update(self, recipe: Recipe) -> None: ...
    async def delete(self, id: int) -> None: ...

class IIngredientStore(Protocol):
    async def create(self, ingredient: Ingredient) -> None: ...
    async def get(self, id: int) -> Ingredient | None: ...
    async def get_all(self) -> list[Ingredient]: ...
    async def update(self, ingredient: Ingredient) -> None: ...
    async def delete(self, id: int) -> None: ...

class IWeeklyPlanStore(Protocol):
    async def create(self, plan: WeeklyPlan) -> None: ...
    async def get(self, id: int) -> WeeklyPlan | None: ...
    async def get_all(self) -> list[WeeklyPlan]: ...
    async def update(self, plan: WeeklyPlan) -> None: ...
    async def delete(self, id: int) -> None: ...

class IShoppingItemStore(Protocol):
    async def create(self, item: ShoppingItem) -> None: ...
    async def get(self, id: int) -> ShoppingItem | None: ...
    async def get_all(self) -> list[ShoppingItem]: ...
    async def get_by_weekly_plan(self, weekly_plan_id: int) -> list[ShoppingItem]: ...
    async def update(self, id: int, item: ShoppingItem) -> None: ...
    async def delete(self, id: int) -> None: ...
```

`WeeklyPlan` and `ShoppingItem` both use a DB-assigned `id` as their primary key. `ShoppingItem` rows are owned by a `WeeklyPlan` — `ON DELETE CASCADE` removes them when the plan is deleted. `get_by_weekly_plan()` is the primary access pattern for fetching a week's shopping list.

## Implementation Notes

- All stores call `get_db()` at method call time (not at construction) — no constructor arguments needed.
- `Recipe.create` inserts the recipe row then inserts each ingredient row in the same transaction.
- `Recipe.update` deletes all existing ingredient rows for that `recipe_id` and re-inserts from the updated model (simpler than diffing).
- `Recipe.get` / `get_all` JOINs with `ingredients` and groups results by recipe id to reconstruct `list[Ingredient]`.
- JSON columns (`instructions`, `tags`, `recipe_ids`) use `json.dumps` on write and `json.loads` on read.
- Dates stored as ISO strings (`datetime.isoformat()` / `date.isoformat()`), parsed back with `datetime.fromisoformat()` / `date.fromisoformat()`.
- `yoyo-migrations` must be added as a project dependency (`uv add yoyo-migrations`).
