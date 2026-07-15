# Forkcast

An AI Agent helping you solve one of the hardest questions out there:

> "What to eat for dinner?"

Use a Telegram Bot to interact with the Agent.

## Commands

### Backend Commands

The backend lives in `backend/`. Run all `uv` commands from `backend/`.

```bash
# Backend (run from backend/)
cd backend

# Install dependencies
uv sync

# Run the backend + frontend together for local dev (open http://localhost:5173)
uv run python scripts/dev.py

# (If you want to) Run the backend only 
uv run python main.py

# Run all tests
uv run pytest

# Run a single test
uv run pytest tests/test_foo.py::test_bar

# Lint and format
uv run ruff check .
uv run ruff format .
```

### Frontend Commands

The React frontend lives in `frontend/`.

```bash
# Frontend (run from frontend/)
cd frontend
npm install       # first-time setup
npm run dev       # dev server (proxies API to :8000)
npm run build     # production build -> frontend/dist
```

## Frontend

The React frontend is served differently in development and production.

**Development — two servers.** Run `uv run python scripts/dev.py` (from `backend/`) to start
both at once:

| Server | Port | Serves the frontend from | Rebuilds on save? |
| --- | --- | --- | --- |
| FastAPI backend | `:8000` | — (API only) | — |
| Vite dev server | `:5173` | `frontend/src` (live) | ✅ hot module reload |

**Open http://localhost:5173 for development.** Vite serves your source files directly and
hot-reloads on every save, so frontend changes appear instantly — no build step. It proxies
the API routes (`/auth`, `/users`, `/chat`, `/meal-plans`, `/recipes`, `/healthcheck`) to the
backend on `:8000`, so calls stay same-origin locally (leave `VITE_API_BASE` unset).

> ⚠️ **DO NOT** open http://localhost:8000 during development. The backend is API-only and
> serves no frontend — use `:5173`.

**Production — two deploys.** The SPA builds with `npm run build` and is hosted on
**Vercel** at `app.forkcast.app`; `frontend/vercel.json` just serves `index.html` for client
routes (SPA fallback). It calls the API **directly** at `https://api.forkcast.app` — set
`VITE_API_BASE=https://api.forkcast.app` in the Vercel project. The FastAPI backend runs on
**Railway** at `api.forkcast.app` (the `Dockerfile`, API only).

The app and API are the **same site** (`forkcast.app`), so the `Lax` session cookie rides on
the cross-origin calls with no `SameSite=None` needed. The backend enables CORS with
credentials for the app origin — add `https://app.forkcast.app` to `CORS_ALLOW_ORIGINS`, and
set `ENVIRONMENT=production` so the cookie is `Secure`.

**OAuth.** In production keep `GOOGLE_REDIRECT_URI=https://api.forkcast.app/auth/google/callback`
(the OAuth round-trip runs against the API host), and set `FRONTEND_URL=https://app.forkcast.app`
so login/logout redirect back to the app.

## Landing Page

The public marketing site lives in `landing/` and is a **separate** [Astro](https://astro.build/)
app — not part of the React SPA in `frontend/`. It builds to pre-rendered static HTML for SEO and
deploys independently to a CDN at the apex domain, while the authenticated app runs on the `app.`
subdomain.

```bash
# Landing (run from landing/)
cd landing
npm install       # first-time setup
npm run dev       # dev server (http://localhost:4321)
npm run build     # static build -> landing/dist
npm run preview   # preview the production build
```

**SEO.** `src/layouts/Layout.astro` holds the per-page `<title>`, meta description, canonical, and
Open Graph / Twitter tags. `@astrojs/sitemap` emits `sitemap-index.xml`, and `public/robots.txt`
points at it. Before deploying, set your real apex domain in **two** places (both use an
`example.com` placeholder): `site:` in `astro.config.mjs` and the `Sitemap:` line in
`public/robots.txt`.

**Interactivity.** The page is fully static HTML except the email capture form
(`src/components/SignupForm.tsx`), which hydrates as a React island. Point it at your email service
by setting `PUBLIC_SIGNUP_ENDPOINT` (it POSTs `{ "email": "..." }`).

**Deploy.** `npm run build` outputs `landing/dist`; deploy that directory to your CDN
(Cloudflare Pages / Netlify / Vercel) with build command `npm run build` and output dir `dist`.
No Dockerfile changes — the landing deploy is fully decoupled from the backend.

## Environment

Create an `.env` file in `/backend/.env`. See `.env.example` for details of required/optional environment variables.

*Create a `.env.test` file in `/backend/.env.test for a separated test environment.*

## Database Setup

The app requires a running PostgreSQL instance. The quickest way is Docker:

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

[yoyo](https://ollycope.com/software/yoyo/latest/) is used for running schema migrations against Postgres. Migrations run synchronously at startup before the bot begins accepting messages. No manual step required.

To add a new migration, create `migrations/NNN-migration-name.sql`. It will be applied automatically on next startup.

## Prompt Management

System prompts are versioned and stored in the `prompts` table in Postgres. This lets you update prompts without redeploying the bot — the active version for each prompt type is loaded at runtime.

There are three prompt types:

| Type | Used by |
| --- | --- |
| `agent` | Main agent reasoning loop |
| `plan` | Meal plan generation |
| `parse_recipe` | Recipe parsing |

Each type has at most one active version at a time. If no active prompt is found for a type, the node falls back to its hardcoded default.

### CLI

Use `manage_prompts.py` to insert and manage prompt versions:

```bash
# Prefix the command with your DATABASE_URL.
# e.g. DATABASE_URL="postgresql://postgres:postgres@localhost:5432/mealprep"

# Backend (run from backend/)
cd backend

# Add a new prompt version (--active promotes it immediately)
DATABASE_URL=<DATABASE_URL> uv run python manage_prompts.py add \
  --type classifier \
  --version 2 \
  --file prompts/classifier_v2.txt \
  --notes "tightened parse_recipe examples" \
  --active

# List all prompts across all types
DATABASE_URL=<DATABASE_URL> uv run python manage_prompts.py list

# Promote a specific version by id
DATABASE_URL=<DATABASE_URL> uv run python manage_prompts.py activate 5
```

*Activating a version automatically deactivates all other versions of the same type.*

## Agentic Workflow (LangGraph)

The agent is built as a [LangGraph](https://langchain-ai.github.io/langgraph/) `StateGraph`. Each Telegram message is a graph invocation; nodes read and write a shared `BotState` that flows through the graph.

### State

```python
class BotState(TypedDict):
    chat_id: int
    messages: list[BaseMessage]
    user_message: str
    pending_recipe: Recipe | None
```

### Graph structure

```plaintext
START
  ↓
agent ←──────────────────────────────┐
  ↓ (tool_calls present)             │
tools ──────────────────────────────→┘
  ↓ (pending_recipe set)
confirm_recipe (interrupt)
  ├→ save_recipe    → END
  └→ discard_recipe → END

agent → END  (no tool calls, no pending recipe)
agent → max_turns_reached → END  (safety limit: 10 turns)
```

Routing:
- `should_continue`: tool calls present → `tools`; max turns exceeded → `max_turns_reached`; else → `END`
- `after_tools`: `pending_recipe` set → `confirm_recipe`; else → back to `agent`

### Tools

| Tool | Description |
| --- | --- |
| `create_meal_plan()` | Generates and persists a weekly meal plan via `MealPlanWorkflow` |
| `get_meal_plan()` | Retrieves the current week's meal plan |
| `parse_recipe_url(url)` | Parses a recipe from a URL via `ParseRecipeWorkflow`; triggers the confirm flow |
| `get_shopping_list()` | Returns the shopping list for the current week's plan |

### Human-in-the-loop (interrupt)

Recipe parsing is a two-turn flow. After `parse_recipe` extracts a recipe, the graph pauses at `confirm_recipe` using LangGraph's `interrupt()`. The bot sends the parsed recipe plus a confirmation prompt to the user, then halts.

On the next message, the handler checks `graph.aget_state(config).next` — if the graph is paused, it resumes via `Command(resume=user_message)` instead of starting a new invocation. The user's reply routes to either `save_recipe` (persists to DB + embeds) or `discard_recipe`.

### Checkpointing

LangGraph's `AsyncPostgresSaver` backs the checkpointer, storing graph state in the same PostgreSQL database used for recipes. Each Telegram `chat_id` maps to a LangGraph `thread_id`, giving every user an isolated, persistent conversation thread. The checkpointer is created at startup inside an `AsyncExitStack` so its connection pool is cleanly closed on shutdown.

This means graph state — including an in-progress recipe confirmation — survives bot restarts.

## RAG (Retrieval-Augmented Generation)

RAG is used to surface relevant recipes when building a meal plan, avoiding the need to pass your entire recipe library to Claude on every request.

**How it works:**

1. **Embedding** — When a recipe is saved, its name, tags, ingredients, and cook time are embedded via [VoyageAI](https://www.voyageai.com/) (`voyage-4`) and stored in a [ChromaDB](https://www.trychroma.com/) collection named `recipes`.
2. **Reconciliation** — On startup, any recipes without embeddings are backfilled so the vector store stays in sync with the database.
3. **Retrieval** — When a meal plan is requested, a semantic search (`k=10`) is run against the vector store. The top results, combined with last week's selections for variety, form the recipe bank passed to Claude.
4. **Selection** — Claude Sonnet picks 5 weekday dinners from that bank and returns structured output (recipe IDs + rationale).

This keeps prompt size bounded and improves selection quality by giving Claude a curated, contextually relevant subset of recipes rather than an unbounded list.

## Observability (Langfuse)

Langfuse traces every LangGraph invocation when credentials are present. If the Langfuse env vars are missing or auth fails, the bot starts normally with tracing disabled — no hard dependency on the service.

**What gets traced:**

- Every graph run: node-by-node execution, latency, and total duration
- Each Claude API call: model, prompt, completion, token counts, and cost
- Prompt cache hit/miss via Anthropic's usage fields

## Design Decisions

- **Prompt caching** — All system prompts use `cache_control: ephemeral`, reducing latency and token cost on repeated calls.
- **Forced tool schema** — The classifier uses a constrained tool definition to guarantee structured JSON output; no free-text parsing or regex needed.
- **Conversation history** — SQLite-backed message store scoped per user, injected as context into the chat workflow.
- **Atomic writes** — Storage uses `.tmp` → `os.replace()` + `asyncio.Lock` to prevent partial writes under concurrent requests.

## Roadmap

### Evals

- Offline eval harness: given a fixed recipe bank + user message, assert the selected meals satisfy constraints (variety, calorie targets, user preferences)
- Classification accuracy tracking: log `(input, predicted_intent, ground_truth)` triples and run a nightly eval job
- LLM-as-judge: use Claude to score meal plan quality across dimensions like balance and variety

### Human Feedback Loop

- After each meal plan, prompt the user to rate it (👍/👎); store ratings and bias future selection accordingly
- Surface low-rated meals as negative examples in the selection prompt

### Guardrails & Safety

- Output validation on `save_recipe`: reject implausible calorie counts or structurally invalid recipes before persisting
