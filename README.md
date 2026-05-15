# Meal Prep Agent

An AI Agent helping you solve one of the hardest questions out there:

> "What to eat for dinner?"

Use a Telegram Bot to interact with the Agent.

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

## Environment

Create an `.env` file at root and fill in:

- `ANTHROPIC_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `DB_PATH` (default: `.data/meal_prep.db`)
- `VECTOR_DB_PATH` (default: `.chroma`)


## Architecture

A Telegram bot that uses Claude AI for meal planning. Messages are intent-classified, then routed to a workflow that calls Claude to select recipes or parse new ones.

```plaintext
Telegram Message
      ↓
Intent Classifier (claude-haiku-4-5, forced tool schema)
      ├→ "plan"       → MealPlanWorkflow (claude-sonnet-4-6)
      ├→ "add_recipe" → AddRecipeWorkflow (claude-sonnet-4-6)
      └→ "chat"       → ChatWorkflow (claude-sonnet-4-6 + history)
```

## Design Decisions

- **Multi-model routing** — `claude-haiku-4-5` for intent classification (fast, cheap); `claude-sonnet-4-6` for meal planning and recipe parsing (capable). Cost is optimized at the routing layer, not as an afterthought.
- **Prompt caching** — All system prompts use `cache_control: ephemeral`, reducing latency and token cost on repeated calls.
- **Forced tool schema** — The classifier uses a constrained tool definition to guarantee structured JSON output; no free-text parsing or regex needed.
- **Conversation history** — SQLite-backed message store scoped per user, injected as context into the chat workflow.
- **Atomic writes** — Storage uses `.tmp` → `os.replace()` + `asyncio.Lock` to prevent partial writes under concurrent requests.

## Roadmap

### Observability

- Integrate [Langfuse](https://langfuse.com) to trace every Claude API call: prompt, completion, model, latency, token counts, and cost per request
- Add a `/stats` Telegram command surfacing weekly token spend and cache hit rate

### Evals

- Offline eval harness: given a fixed recipe bank + user message, assert the selected meals satisfy constraints (variety, calorie targets, user preferences)
- Classification accuracy tracking: log `(input, predicted_intent, ground_truth)` triples and run a nightly eval job
- LLM-as-judge: use Claude to score meal plan quality across dimensions like balance and variety

### Retrieval / RAG

- Replace linear recipe scan with semantic search over recipe embeddings so queries like "something light and Asian" work without keyword matching

### Multi-modal

- Accept food photos via Telegram; use Claude's vision input to parse a recipe from a photo or menu screenshot

### Human Feedback Loop

- After each meal plan, prompt the user to rate it (👍/👎); store ratings and bias future selection accordingly
- Surface low-rated meals as negative examples in the selection prompt

### Guardrails & Safety

- Output validation on `save_recipe`: reject implausible calorie counts or structurally invalid recipes before persisting

### Prompt Management

- Version system prompts in `agent/prompts.py` with a `version` field so A/B tests and regressions are traceable in Langfuse
