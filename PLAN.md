# Meal Prep Agent — Build Plan

## What This Bot Does

1. User asks "plan my meals for the week" via Telegram
2. Bot reads last week's Meal Plan from disk (to know what was eaten)
3. Bot loads the entire Recipe Bank from disk
4. Claude selects 7 new recipes with minimal overlap with last week
5. Bot aggregates all ingredients → Shopping List
6. Bot sends the plan + shopping list back via Telegram
7. Bot saves the new weekly plan to disk (referenced next week)
8. Bot cleans up plans older than 4 weeks

Second skill: Add new recipes to the Recipe Bank via Telegram.

---

## Architecture: Workflow, Not Agent

Code controls orchestration. Claude handles selection and parsing — it does not orchestrate itself.

```
Telegram Message
      │
      ▼
Intent Classifier (claude-haiku-4-5)
      │
      ├── "plan"        → MealPlanWorkflow
      ├── "add_recipe"  → AddRecipeWorkflow
      └── "chat"        → ChatWorkflow
```

---

## Data Layout

```
data/                           ← gitignored, created at runtime
  recipes.json                  ← Recipe Bank (JSON dict keyed by recipe id)
  meal_prep.db                  ← SQLite (conversation history only)
  meal_plans/
    2026-W15.json               ← ISO week format
    2026-W16.json               ← max 4 files kept
```

SQLite is retained only for conversation history. All domain data (recipes, plans) lives in JSON files.

---

## Phase 1 — Data Models (`models/domain.py`)

Four Pydantic models:

```python
class Ingredient(BaseModel):
    name: str
    amount: float
    unit: str           # "" for count-based items ("2 eggs")

class Recipe(BaseModel):
    id: str             # URL-safe slug, e.g. "chicken-stir-fry"
    name: str
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"]
    servings: int
    prep_minutes: int
    cook_minutes: int
    ingredients: list[Ingredient]
    instructions: list[str]
    tags: list[str]
    created_at: datetime

class WeeklyPlan(BaseModel):
    week_label: str         # ISO week e.g. "2026-W16"
    recipe_ids: list[str]   # exactly 7 entries, ordered Mon–Sun
    notes: str              # Claude's rationale / overlap caveats
    created_at: datetime

class ShoppingItem(BaseModel):
    ingredient_name: str
    total_amount: float
    unit: str
    recipe_sources: list[str]   # which recipe IDs contribute this item
    # computed in-memory only; never written to disk
```

`models/__init__.py` re-exports all four models.

---

## Phase 2 — Storage Layer (`storage/`)

### `storage/recipe_bank.py` — RecipeBank

Single file: `data/recipes.json` (dict keyed by recipe `id`).

```python
async def load_all(self) -> dict[str, Recipe]       # {} if file missing
async def get(self, recipe_id: str) -> Recipe | None
async def save_recipe(self, recipe: Recipe)         # atomic write: .tmp → os.replace()
async def exists(self, recipe_id: str) -> bool
```

File writes are protected by an `asyncio.Lock` on the class instance.

### `storage/plan_store.py` — PlanStore

One file per week under `data/meal_plans/`.

```python
async def save_plan(self, plan: WeeklyPlan)
async def load_latest_plan(self) -> WeeklyPlan | None   # None if no history
async def list_week_labels(self) -> list[str]           # sorted oldest-first
async def cleanup_old_plans(self, keep: int = 4) -> list[str]  # returns deleted labels
@staticmethod def current_week_label() -> str   # datetime.now().strftime("%G-W%V")
```

ISO week labels sort lexicographically: `2026-W09` < `2026-W16` < `2027-W01`. Always zero-pad week numbers.

### `storage/db.py` — ConversationStore

```sql
CREATE TABLE conversation_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    role        TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

```python
async def init(self)
async def append(self, telegram_id: int, role: str, content: str)
async def get_history(self, telegram_id: int, limit: int = 20) -> list[dict]
async def clear_history(self, telegram_id: int)
```

`storage/__init__.py` re-exports `RecipeBank`, `PlanStore`, `ConversationStore`.

---

## Phase 3 — Claude Integration (`agent/`)

### `agent/tools.py` — Tool Definitions

**`select_meal_plan`** — used in MealPlanWorkflow:
```python
{
    "name": "select_meal_plan",
    "description": "Select exactly 7 recipes from the recipe bank for the upcoming week. Minimize overlap with last week. Always call this tool.",
    "input_schema": {
        "type": "object",
        "properties": {
            "recipe_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 7,
                "maxItems": 7
            },
            "notes": {"type": "string"}   # rationale + any caveats
        },
        "required": ["recipe_ids", "notes"]
    }
}
```

**`save_recipe`** — used in AddRecipeWorkflow:
```python
{
    "name": "save_recipe",
    "description": "Parse the user's recipe description and save it. Infer all fields. Always call this tool.",
    "input_schema": {
        "type": "object",
        "properties": {
            "id":            {"type": "string"},   # URL-safe slug
            "name":          {"type": "string"},
            "meal_type":     {"type": "string", "enum": ["breakfast","lunch","dinner","snack"]},
            "servings":      {"type": "integer", "minimum": 1},
            "prep_minutes":  {"type": "integer", "minimum": 0},
            "cook_minutes":  {"type": "integer", "minimum": 0},
            "ingredients":   {"type": "array", "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "amount": {"type": "number"}, "unit": {"type": "string"}},
                "required": ["name", "amount", "unit"]
            }},
            "instructions":  {"type": "array", "items": {"type": "string"}},
            "tags":          {"type": "array", "items": {"type": "string"}}
        },
        "required": ["id","name","meal_type","servings","prep_minutes","cook_minutes","ingredients","instructions","tags"]
    }
}
```

### `agent/prompts.py` — System Prompts

**MEAL_PLAN_SYSTEM**: Instructs Claude to call `select_meal_plan()` with exactly 7 IDs from the provided bank. Minimize overlap with `previous_ids`. Vary meal types across the week. If bank has fewer than 7 recipes, repeat least-recently-used ones. Never respond with plain text.

**ADD_RECIPE_SYSTEM**: Instructs Claude to parse the user's natural-language description and call `save_recipe()`. Infer reasonable defaults for missing fields. Generate a clean URL-safe slug for `id`. Never respond with plain text.

**CHAT_SYSTEM**: Friendly meal prep assistant. Format for Telegram (`*bold*`, bullet points, ≤4096 chars).

### `agent/classifier.py` — Intent Classification

```python
class Intent(str, Enum):
    PLAN = "plan"
    ADD_RECIPE = "add_recipe"
    CHAT = "chat"

class ClassifiedIntent(BaseModel):
    intent: Intent
    confidence: float

async def classify(message: str, client: AsyncAnthropic) -> ClassifiedIntent
```

Single call to `claude-haiku-4-5` with a forced tool schema that returns `ClassifiedIntent`. Cheap — runs on every message.

---

## Phase 4 — Workflows (`agent/workflows.py`)

All three workflows live in one module. Each is an `async` function returning a Telegram-formatted string.

### MealPlanWorkflow

```
1. recipe_bank.load_all()
   → if empty: return "Your recipe bank is empty. Add recipes first."

2. plan_store.load_latest_plan()
   → previous_ids = plan.recipe_ids if plan else []

3. Build Claude user message:
   - compact JSON of bank: {id: {name, tags}} (not full objects — keeps context lean)
   - previous_ids list

4. client.messages.create(
       model="claude-sonnet-4-6",
       system=[{text: MEAL_PLAN_SYSTEM, cache_control: {type: "ephemeral"}}],
       tools=[SELECT_MEAL_PLAN_TOOL],
       tool_choice={"type": "tool", "name": "select_meal_plan"},
       messages=[{"role": "user", "content": user_context}]
   )

5. Extract: selected_ids = response.content[0].input["recipe_ids"]
            notes         = response.content[0].input["notes"]

6. Validate selected IDs exist in bank.
   For any hallucinated IDs, substitute real IDs from bank
   (prefer IDs not in previous_ids, fallback to any).

7. selected_recipes = [bank[id] for id in selected_ids]
   shopping = aggregate_ingredients(selected_recipes)
   # pure function: group by (name.lower(), unit.lower()), sum amounts

8. plan = WeeklyPlan(week_label=current_week_label(), recipe_ids=selected_ids, notes=notes, ...)
   await plan_store.save_plan(plan)
   await plan_store.cleanup_old_plans(keep=4)

9. return format_meal_plan_response(plan, bank, shopping)
```

**aggregate_ingredients (pure function):**
Groups `ShoppingItem` by `(ingredient_name.lower(), unit.lower())`, sums `total_amount`. Different units for the same ingredient remain as separate items (no unit conversion).

### AddRecipeWorkflow

```
1. client.messages.create(
       system=[{text: ADD_RECIPE_SYSTEM, cache_control: {type: "ephemeral"}}],
       tools=[SAVE_RECIPE_TOOL],
       tool_choice={"type": "tool", "name": "save_recipe"},
       messages=[{"role": "user", "content": user_message}]
   )

2. tool_input = response.content[0].input
   tool_input["created_at"] = datetime.now().isoformat()

3. try:
       recipe = Recipe.model_validate(tool_input)
   except ValidationError as e:
       return f"Couldn't parse that recipe: {e.errors()[0]['msg']}"

4. if await recipe_bank.exists(recipe.id):
       recipe = recipe.model_copy(update={"id": f"{recipe.id}-{int(time.time())}"})

5. await recipe_bank.save_recipe(recipe)
   return f"Saved: *{recipe.name}* (`{recipe.id}`)\n{len(recipe.ingredients)} ingredients, {recipe.prep_minutes + recipe.cook_minutes} min"
```

### ChatWorkflow

```
1. history = await conv_store.get_history(telegram_id, limit=20)
2. messages = history + [{"role": "user", "content": user_message}]
3. response = client.messages.create(system=CHAT_SYSTEM, messages=messages, ...)
4. await conv_store.append(telegram_id, "user", user_message)
   await conv_store.append(telegram_id, "assistant", reply)
5. return reply
```

### `agent/router.py` — Route dispatcher

```python
async def route(telegram_id, user_message, recipe_bank, plan_store, conv_store, client) -> str:
    intent = await classify(user_message, client)
    match intent.intent:
        case Intent.PLAN:       return await MealPlanWorkflow(...)
        case Intent.ADD_RECIPE: return await AddRecipeWorkflow(...)
        case Intent.CHAT:       return await ChatWorkflow(...)
```

---

## Phase 5 — Telegram Bot (`bot/`)

### `bot/handlers.py`

```python
async def handle_message(update, context):
    # resources from context.bot_data: recipe_bank, plan_store, conv_store, client
    await context.bot.send_chat_action(chat_id=..., action="typing")
    reply = await route(telegram_id, user_message, ...)
    for chunk in split_message(reply, limit=4096):  # split on newlines at limit
        await update.message.reply_text(chunk, parse_mode="Markdown")
```

Commands: `/start` (welcome), `/reset` (clear conversation history), `/help`

### `bot/keyboards.py`

```python
def plan_confirmation_keyboard() -> InlineKeyboardMarkup:
    # "Save plan" | "Regenerate" — optional for MVP
```

### `bot/main.py`

```python
async def post_init(application):
    conv_store = ConversationStore(os.getenv("DB_PATH", "data/meal_prep.db"))
    await conv_store.init()
    application.bot_data["recipe_bank"]      = RecipeBank()
    application.bot_data["plan_store"]       = PlanStore()
    application.bot_data["conv_store"]       = conv_store
    application.bot_data["anthropic_client"] = AsyncAnthropic(api_key=...)
```

`Application.post_init` runs after the event loop starts but before polling — the correct place for async initialization in `python-telegram-bot` v21.

---

## Phase 6 — Polish

- Add `cache_control: {"type": "ephemeral"}` to all system prompt blocks (already shown in workflows above)
- Typing indicator before every Claude call (`ChatAction.TYPING`)
- `split_message(text, limit=4096)` — split on newlines to respect Telegram's char limit
- Seed `data/recipes.json` manually with 10+ example recipes for first-run testing
- Wrap all Claude calls in `try/except anthropic.APIError` — return friendly error string

---

## Edge Case Handling

| Situation | Handling |
|---|---|
| Empty recipe bank | Fail early before Claude call; return "Add recipes first" |
| No previous week plan | Pass `previous_ids=[]`; Claude still selects 7 |
| Bank has fewer than 7 recipes | Claude repeats least-recently-used; code validates all IDs exist |
| Claude returns hallucinated IDs | Validate after tool call; substitute real bank IDs for invalid ones |
| Duplicate recipe ID on add | Append Unix timestamp suffix to ID before saving |
| Telegram 4096-char limit | `split_message()` splits on newlines at the boundary |

---

## File Checklist

```
models/
  __init__.py          ← re-exports all models
  domain.py            ← Ingredient, Recipe, WeeklyPlan, ShoppingItem

storage/
  __init__.py          ← re-exports RecipeBank, PlanStore, ConversationStore
  recipe_bank.py       ← RecipeBank (data/recipes.json)
  plan_store.py        ← PlanStore (data/meal_plans/*.json + cleanup)
  db.py                ← ConversationStore (SQLite, conversation history)

agent/
  __init__.py
  classifier.py        ← classify() → ClassifiedIntent       [Phase 3]
  tools.py             ← SELECT_MEAL_PLAN_TOOL, SAVE_RECIPE_TOOL  [Phase 3]
  prompts.py           ← MEAL_PLAN_SYSTEM, ADD_RECIPE_SYSTEM, CHAT_SYSTEM  [Phase 3]
  workflows.py         ← MealPlanWorkflow, AddRecipeWorkflow, ChatWorkflow  [Phase 4]
  router.py            ← route() dispatcher                   [Phase 4]

bot/
  __init__.py
  handlers.py          ← Telegram handlers + split_message    [Phase 5]
  keyboards.py         ← InlineKeyboard helpers               [Phase 5]
  main.py              ← Application setup + run_polling      [Phase 5]

tools/
  __init__.py          ← empty (scaffold artifact, not used)

main.py                ← entry point: load_dotenv, call bot/main.py

data/                  ← gitignored, created at runtime
  recipes.json         ← starts as {}
  meal_plans/          ← directory created at startup
```

---

## Build Order

1. `models/domain.py` — no dependencies; defines all contracts
2. `storage/recipe_bank.py` + `storage/plan_store.py` + `storage/db.py`
3. `agent/tools.py` + `agent/prompts.py` — static definitions
4. `agent/workflows.py` + `agent/router.py` — core logic
5. `agent/classifier.py`
6. `bot/handlers.py` + `bot/keyboards.py` + `bot/main.py`
7. `main.py`
8. Phase 6: prompt caching, error handling, seed recipes, typing indicators

---

## Verification

1. **RecipeBank**: add a recipe programmatically → verify `data/recipes.json` has correct structure
2. **PlanStore cleanup**: create 5 plan files manually → run `cleanup_old_plans(keep=4)` → verify oldest deleted
3. **AddRecipe flow**: send "add recipe: grilled salmon, 2 fillets, olive oil, lemon, 20 min" to bot → verify entry in `data/recipes.json`
4. **MealPlan — empty bank**: with no recipes, type "plan my meals" → bot returns helpful error without calling Claude
5. **MealPlan — full flow**: with 10+ recipes in bank, type "plan my meals for the week" → verify:
   - 7 distinct recipe names in response
   - Shopping list shows aggregated ingredients
   - `data/meal_plans/{current-week}.json` exists on disk
6. **Overlap check**: run the plan twice in consecutive weeks → second week's plan should differ from first
7. **Cleanup**: manually add 5+ plan files → trigger `/plan` → verify only 4 newest remain
