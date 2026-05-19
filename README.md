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

Create an `.env` file at root. See `.env.example`.

- `ANTHROPIC_API_KEY`
- `CHROMA_HOST`
- `CHROMA_PORT`
- `DATABASE_URL`
- `TELEGRAM_BOT_TOKEN`
- `VOYAGE_API_KEY`

## Database Setup

Meal Prep Agent requires a running PostgreSQL instance. The quickest way is Docker:

```bash
docker run -d \
  --name mealprep-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=mealprep \
  -p 5432:5432 \
  postgres:16
```

Then set `DATABASE_URL` in your `.env`:

```env
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/mealprep"
```

Use a separate config for your tests in `.env.test` so they will be isolated since we need to reset the database after every test:

```env
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/mealprep_test"
```

To stop and remove the container:

```bash
docker stop mealprep-postgres && docker rm mealprep-postgres
```

### Migrations

Meal Prep Agent uses [yoyo](https://ollycope.com/software/yoyo/latest/) for schema migrations against Postgres. Migrations run synchronously at startup before the bot begins accepting messages. No manual step required.

To add a new migration, create `migrations/NNN-migration-name.sql`. It will be applied automatically on next startup.

## Architecture

A Telegram bot that uses Claude AI for meal planning. Messages are intent-classified, then routed to a workflow that calls Claude to select recipes or parse new ones.

```plaintext
Telegram Message
      ↓
Intent Classifier (claude-haiku-4-5)
      ├→ "plan"         → MealPlanWorkflow (claude-sonnet-4-6)
      ├→ "parse_recipe" → ParseRecipeWorkflow (claude-sonnet-4-6)
      └→ "chat"         → ChatWorkflow (claude-sonnet-4-6) # not implemented yet
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

### Multi-modal

- Accept food photos via Telegram; use Claude's vision input to parse a recipe from a photo or menu screenshot

### Human Feedback Loop

- After each meal plan, prompt the user to rate it (👍/👎); store ratings and bias future selection accordingly
- Surface low-rated meals as negative examples in the selection prompt

### Guardrails & Safety

- Output validation on `save_recipe`: reject implausible calorie counts or structurally invalid recipes before persisting

### Prompt Management

- Version system prompts in `agent/prompts.py` with a `version` field so A/B tests and regressions are traceable in Langfuse
