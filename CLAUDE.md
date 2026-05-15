# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the bot
uv run python main.py

# Run all tests
uv run pytest

# Run a single test
uv run pytest tests/test_foo.py::test_bar

# Lint and format
uv run ruff check .
uv run ruff format .
```

## Architecture

A Telegram bot that uses Claude AI for meal planning. Messages are intent-classified, then routed to a workflow that calls Claude to select recipes or parse new ones.

```
Telegram Message
      ↓
Intent Classifier (claude-haiku-4-5, forced tool schema)
      ├→ "plan"       → MealPlanWorkflow (claude-sonnet-4-6)
      ├→ "add_recipe" → AddRecipeWorkflow (claude-sonnet-4-6)
      └→ "chat"       → ChatWorkflow (claude-sonnet-4-6 + history)
```

**Key design choice**: Claude is used only for selection/parsing within each workflow — the code controls all orchestration.

## Module Layout

- `models/domain.py` — Pydantic models: `Ingredient`, `Recipe`, `WeeklyPlan`, `ShoppingItem`
- `storage/recipe_bank.py` — JSON-backed recipe store (`data/recipes.json`)
- `storage/plan_store.py` — Weekly plan storage (`data/meal_plans/<ISO-week>.json`)
- `storage/db.py` — SQLite conversation history (aiosqlite)
- `agent/classifier.py` — Intent classification returning `ClassifiedIntent`
- `agent/tools.py` — Claude tool schemas (`select_meal_plan`, `save_recipe`)
- `agent/prompts.py` — System prompts (all use `cache_control: ephemeral`)
- `agent/workflows.py` — `MealPlanWorkflow`, `AddRecipeWorkflow`, `ChatWorkflow`
- `agent/router.py` — Dispatches to workflow based on intent
- `bot/handlers.py` — Telegram command and message handlers
- `bot/main.py` — Bot startup; stores global shared state in separate modules

## Storage

- Recipes and plans: JSON files with atomic writes (`.tmp` → `os.replace()`), `asyncio.Lock` per store class
- Conversation history: SQLite via aiosqlite
- `data/` directory is gitignored and created at runtime

## Claude API Usage

All system prompts use `cache_control: {"type": "ephemeral"}` for prompt caching. The classifier uses `claude-haiku-4-5`; all workflows use `claude-sonnet-4-6`. Refer to the `claude-api` skill when adding or modifying Claude API calls.

## Environment

Copy `.env.example` to `.env` and fill in:
- `ANTHROPIC_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `DB_PATH` (default: `.data/meal_prep.db`)
- `VECTOR_DB_PATH` (default: `.chroma`)
