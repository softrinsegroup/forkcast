# LangChain → LangGraph Refactor

## Context

Refactoring the meal prep agent in two phases:

- **Phase 1 (LangChain):** Replace raw Anthropic SDK calls, hand-rolled JSON tool schemas, and manual tool-use response parsing with LangChain abstractions (`ChatAnthropic`, `@tool`, `.with_structured_output()`, `ChatPromptTemplate`, LCEL chains). Also migrate the RAG layer from the raw Voyage AI + ChromaDB clients to `VoyageAIEmbeddings` + `langchain-chroma`.
- **Phase 2 (LangGraph):** Replace `agent/router.py`'s match/case dispatch and the `PendingAction` multi-turn hack with a `StateGraph`. The confirm-recipe confirmation flow becomes a proper `interrupt()`. The bot handler becomes thread-aware for per-chat state persistence.

Storage layer (SQLite, stores), Telegram handlers (until Phase 2), domain models, and business logic (ingredient aggregation, formatting) are **not** replaced — these aren't LLM orchestration concerns.

---

## Phase 1: LangChain

### 1.1 — Dependencies

- [x] `uv add langchain-anthropic langchain-core langchain-chroma langchain-voyageai`
- [x] `uv add voyageai` (still needed directly for transactional outbox pattern)
- [x] Add `VOYAGE_API_KEY` to `.env` and `.env.example`

---

### 1.2 — RAG Foundation (do this first — Phase 2 builds on it)

This is the transactional outbox pattern for dual-write consistency between SQLite and ChromaDB.

- [x] **`migrations/002_add_embedded_flag.sql`** (new file)
  ```sql
  ALTER TABLE recipes ADD COLUMN embedded BOOLEAN NOT NULL DEFAULT FALSE;
  ```

- [x] **`storage/recipe_store.py`** — three changes:
  - Fix `create()`: replace broken `async with self.db.execute("BEGIN")` no-op with `async with transaction(self.db)`, return `recipe_id: int`
  - Add `get_unembedded() -> list[Recipe]`: `SELECT * FROM recipes WHERE embedded = FALSE`
  - Add `mark_embedded(recipe_id: int) -> None`: `UPDATE recipes SET embedded = TRUE WHERE id = ?`
  - Update `IRecipeStore` Protocol: new methods + `create` return type `-> int`

- [x] **`storage/vector_store.py`** (new file) — `VectorStore` class using LangChain abstractions:
  - Constructor: `(chroma_store: LangchainChroma, recipe_store: RecipeStore)`
  - `_build_document(recipe) -> str`: `"Recipe: {name}\nTags: ...\nIngredients: ...\nInstructions: ..."`
  - `embed_recipe(recipe_id, recipe) -> None`: add to Chroma, call `mark_embedded()`
  - `query(text, n_results=10) -> list[int]`: similarity search, return recipe IDs
  - `reconcile() -> None`: `get_unembedded()` → embed each, log failures, continue on error
  - Use `langchain_chroma.Chroma` + `langchain_voyageai.VoyageAIEmbeddings(model="voyage-3")`
  - All Chroma calls are sync — wrap with `asyncio.to_thread()`

- [x] **`storage/__init__.py`** — add `from .vector_store import VectorStore`

- [x] **`bot/main.py`** — init `VectorStore` in `post_init`, call `reconcile()` at startup:
  ```python
  embeddings = VoyageAIEmbeddings(model="voyage-3", voyage_api_key=os.getenv("VOYAGE_API_KEY"))
  chroma_store = await asyncio.to_thread(
      Chroma, collection_name="recipes", embedding_function=embeddings,
      persist_directory=os.getenv("VECTOR_DB_PATH", "data/chroma")
  )
  vector_store = VectorStore(chroma_store, recipe_store)
  application.bot_data["vector_store"] = vector_store
  await vector_store.reconcile()
  ```

- [x] **`bot/handlers.py`** — after `recipe_store.create(recipe)`, call `vector_store.embed_recipe()`:
  ```python
  recipe_id = await recipe_store.create(recipe)
  try:
      await vector_store.embed_recipe(recipe_id, recipe)
  except Exception as e:
      print(f"Warning: embedding failed for recipe_id={recipe_id}: {e}")
  ```
  Embedding failure is silent to user — recipe is safe with `embedded=FALSE`, reconcile picks it up on next startup.

---

### 1.3 — Tools: `agent/tools.py`

Replace the three hand-rolled JSON dicts with Pydantic models used by LangChain.

- [x] **`CLASSIFY_INTENT_TOOL`** → `ClassifiedIntent(BaseModel)` with `intent: Literal["plan", "parse_recipe", "chat"]` and `confidence: float`. Used with `.with_structured_output()` — no `@tool` needed.

- [x] **`CREATE_MEAL_PLAN_TOOL`** → `@tool`-decorated function or Pydantic `MealPlanInput(BaseModel)` with `recipe_ids: list[int]` and `notes: str`. Used with `.bind_tools([...], tool_choice="create_meal_plan")`.

- [x] **`PARSE_RECIPE_TOOL`** → `@tool`-decorated function or Pydantic `ParseRecipeInput(BaseModel)` matching the current schema fields. Used the same way.

---

### 1.4 — Prompts: `agent/prompts.py`

Replace raw strings with LangChain prompt objects. Content stays the same.

- [x] `CLASSIFY_INTENT_PROMPT` → `SystemMessage(content=...)`
- [x] `MEAL_PLAN_PROMPT` → `ChatPromptTemplate.from_messages([("system", ...), ("human", "{input}")])`
- [x] `PARSE_RECIPE_PROMPT` → `ChatPromptTemplate.from_messages([("system", ...), ("human", "{url}")])`
- [x] `CHAT_PROMPT` → `SystemMessage(content=...)`

> **Note on prompt caching:** The current code sets `cache_control: {"type": "ephemeral"}` manually. In `langchain-anthropic`, pass this via `extra_headers` on `ChatAnthropic` or use `SystemMessage` with `additional_kwargs={"cache_control": {"type": "ephemeral"}}`.

---

### 1.5 — Classifier: `agent/classifier.py`

Replace manual `client.messages.create()` + tool_use parsing with an LCEL chain.

- [x] Rewrite `classify()` as an LCEL chain:
  ```python
  llm = ChatAnthropic(model="claude-haiku-4-5-20251001")
  chain = classify_prompt | llm.with_structured_output(ClassifiedIntent)
  result: ClassifiedIntent = await chain.ainvoke({"message": message})
  ```
- [x] Remove the `client: AsyncAnthropic` parameter — `ChatAnthropic` self-initializes from `ANTHROPIC_API_KEY`
- [x] Update `agent/router.py` call site to remove `client` arg from `classify()`

---

### 1.6 — MealPlanWorkflow: `agent/workflows/meal_plan.py`

Replace `_get_recommended_recipes()` raw API call and `_fetch_recipe_bank()` with LangChain chain + vector search.

- [ ] `_fetch_recipe_bank()` — replace `recipe_store.get_all()` with `vector_store.query()`:
  ```python
  recipe_ids = await self.vector_store.query("weekly meal plan variety healthy balanced", n_results=20)
  recipes = [await self.recipe_store.get(rid) for rid in recipe_ids] if recipe_ids else await self.recipe_store.get_all()
  self.recipe_bank = {r.id: r for r in recipes if r is not None}
  ```
- [ ] `_get_recommended_recipes()` — replace raw `client.messages.create()` with LCEL chain:
  ```python
  llm = ChatAnthropic(model="claude-sonnet-4-6")
  chain = meal_plan_prompt | llm.bind_tools([create_meal_plan_tool], tool_choice="create_meal_plan")
  response = await chain.ainvoke({"input": message})
  # Parse tool call from response.tool_calls[0]
  ```
- [ ] Add `vector_store: VectorStore` constructor param
- [ ] Update `agent/router.py` to pass `vector_store` to `MealPlanWorkflow(...)`
- [ ] Update `bot/handlers.py` `handle_message()` to pass `context.bot_data["vector_store"]` to `route()`

---

### 1.7 — ParseRecipeWorkflow: `agent/workflows/parse_recipe.py`

Replace raw loop with LCEL chain. This workflow uses Anthropic's built-in `web_fetch` server-side tool and the `pause_turn` stop reason.

- [ ] Replace `_parse_url()` raw loop with:
  ```python
  llm = ChatAnthropic(model="claude-sonnet-4-6")
  chain = parse_recipe_prompt | llm.bind_tools(
      [{"type": "web_fetch_20260209", "name": "web_fetch"}, parse_recipe_tool]
  )
  response = await chain.ainvoke({"url": self.url})
  ```
- [ ] `langchain-anthropic` handles `pause_turn` transparently in recent versions (it loops internally). Verify this behavior holds — if not, keep the manual loop and wrap only the LLM construction.
- [ ] Parse structured output from `response.tool_calls[0]["args"]` and validate into `Recipe` with `Recipe.model_validate({...})`

---

### 1.8 — ChatWorkflow: `agent/workflows/chat.py`

Currently returns a hardcoded string with no LLM call. Add a real chat response.

- [ ] Add LLM call using `ChatAnthropic` + `chat_prompt | llm` chain
- [ ] Accept `chat_history: list` parameter (pass from `bot_data` or `context.user_data`)
- [ ] Use `RunnableWithMessageHistory` if wiring up persistent chat history

---

### 1.9 — Router: `agent/router.py`

- [ ] Remove `client: AsyncAnthropic` param (no longer passed to `classify()`)
- [ ] Instantiate `ChatAnthropic` instances inside each workflow constructor, not in `route()`
- [ ] Add `vector_store: VectorStore` param, forward to `MealPlanWorkflow`
- [ ] Update `bot/handlers.py` `handle_message()` call site accordingly

---

### 1.10 — Phase 1 Verification

- [ ] `uv run ruff check . && uv run ruff format .`
- [ ] `uv run pytest`
- [ ] Manual: send "plan my meals" → verify meal plan returns with vector-retrieved recipes
- [ ] Manual: send a recipe URL → verify parsed recipe confirmation flow still works
- [ ] Manual: save recipe → `SELECT embedded FROM recipes ORDER BY id DESC LIMIT 1;` → should be `1`
- [ ] Manual: restart bot with an unembedded recipe → console logs `"reconciling 1 unembedded recipe(s)..."`

---

## Phase 2: LangGraph

### 2.1 — Dependencies

- [ ] `uv add langgraph langgraph-checkpoint-sqlite`

---

### 2.2 — State Schema: new file `agent/state.py`

Define the shared state that flows through the graph.

- [ ] Create `BotState(TypedDict)`:
  ```python
  class BotState(TypedDict):
      chat_id: int
      user_message: str
      intent: str | None
      reply: str | None
      pending_recipe: Recipe | None   # replaces PendingAction
  ```

---

### 2.3 — Graph Nodes: `agent/graph.py` (new file)

Each node is an async function `(state: BotState) -> dict` returning a partial state update.

- [ ] `classify_node(state)` — calls the LangChain classifier chain from Phase 1, returns `{"intent": ...}`
- [ ] `plan_node(state)` — runs `MealPlanWorkflow`, returns `{"reply": ...}`
- [ ] `parse_recipe_node(state)` — runs `ParseRecipeWorkflow`, returns `{"reply": ..., "pending_recipe": ...}`
- [ ] `confirm_recipe_node(state)` — calls `interrupt()` to pause and wait for user yes/no
- [ ] `save_recipe_node(state)` — saves `state["pending_recipe"]` to `recipe_store` + embeds it
- [ ] `chat_node(state)` — runs `ChatWorkflow`, returns `{"reply": ...}`
- [ ] `intent_router(state) -> str` — conditional edge function: returns node name based on `state["intent"]`
- [ ] `confirm_router(state) -> str` — routes "yes" → `save_recipe`, anything else → `end`

---

### 2.4 — Build the Graph: `agent/graph.py`

- [ ] Wire nodes and edges:
  ```python
  graph = StateGraph(BotState)
  graph.add_node("classify", classify_node)
  graph.add_node("plan", plan_node)
  graph.add_node("parse_recipe", parse_recipe_node)
  graph.add_node("confirm_recipe", confirm_recipe_node)
  graph.add_node("save_recipe", save_recipe_node)
  graph.add_node("chat", chat_node)

  graph.add_edge(START, "classify")
  graph.add_conditional_edges("classify", intent_router, {
      "plan": "plan", "parse_recipe": "parse_recipe", "chat": "chat"
  })
  graph.add_edge("parse_recipe", "confirm_recipe")
  graph.add_conditional_edges("confirm_recipe", confirm_router, {
      "save": "save_recipe", "cancel": END
  })
  graph.add_edge("plan", END)
  graph.add_edge("save_recipe", END)
  graph.add_edge("chat", END)
  ```
- [ ] Compile with `AsyncSqliteSaver` checkpointer:
  ```python
  from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
  checkpointer = AsyncSqliteSaver.from_conn_string("data/langgraph.db")
  compiled_graph = graph.compile(checkpointer=checkpointer, interrupt_before=["confirm_recipe"])
  ```

---

### 2.5 — Replace `PendingAction` with `interrupt()`

- [ ] Delete `PendingAction` from `models/domain.py`
- [ ] Delete `_handle_pending_action()` and `_store_pending_action()` from `bot/handlers.py`
- [ ] `confirm_recipe_node` uses `interrupt()` — graph pauses here and resumes on next user message
- [ ] The yes/no check moves into `confirm_router` as a pure conditional edge function

---

### 2.6 — Update `bot/handlers.py`

The handler becomes thread-aware: each `chat_id` maps to a LangGraph thread.

- [ ] Remove `route()` call and all workflow imports
- [ ] Replace with graph invocation:
  ```python
  config = {"configurable": {"thread_id": str(chat_id)}}
  result = await compiled_graph.ainvoke(
      {"chat_id": chat_id, "user_message": user_message},
      config=config
  )
  reply = result["reply"]
  ```
- [ ] Store `compiled_graph` in `bot_data["graph"]` (initialized in `post_init`)

---

### 2.7 — Update `bot/main.py`

- [ ] Build and compile the graph in `post_init`, store in `bot_data["graph"]`
- [ ] Pass stores and vector_store into graph nodes via closure or partial application
- [ ] Remove `route()` import

---

### 2.8 — Retire `agent/router.py` and `agent/workflows/__init__.py`

- [ ] Delete `agent/router.py` — replaced by graph nodes
- [ ] Delete `agent/workflows/__init__.py` Workflow base class — nodes are plain async functions now
- [ ] Individual workflow files (`meal_plan.py`, `parse_recipe.py`, `chat.py`) become the node function implementations or are inlined into `agent/graph.py`

---

### 2.9 — Phase 2 Verification

- [ ] `uv run ruff check . && uv run ruff format .`
- [ ] `uv run pytest`
- [ ] Manual: send "plan my meals" → full meal plan response
- [ ] Manual: send recipe URL → parsed recipe shown → reply "yes" → saved + embedded
- [ ] Manual: send recipe URL → reply "no" → cancelled, nothing saved
- [ ] Manual: send recipe URL, restart bot, reply "yes" → confirm graph resumes from checkpoint (not lost)
- [ ] Manual: verify two different Telegram chats have independent state (different `thread_id`)

---

## Critical Files Summary

| File | Phase | Action |
|---|---|---|
| `migrations/002_add_embedded_flag.sql` | 1 | New |
| `storage/recipe_store.py` | 1 | Fix `create()`, add `get_unembedded()`, `mark_embedded()` |
| `storage/vector_store.py` | 1 | New — LangChain-based `VectorStore` |
| `storage/__init__.py` | 1 | Export `VectorStore` |
| `agent/tools.py` | 1 | Replace JSON dicts with Pydantic models / `@tool` |
| `agent/prompts.py` | 1 | Replace strings with `ChatPromptTemplate` / `SystemMessage` |
| `agent/classifier.py` | 1 | LCEL chain with `.with_structured_output()` |
| `agent/workflows/meal_plan.py` | 1 | LCEL chain + vector search |
| `agent/workflows/parse_recipe.py` | 1 | LCEL chain with `web_fetch` tool |
| `agent/workflows/chat.py` | 1 | Real LLM call + message history |
| `agent/router.py` | 1→2 | Simplified in Phase 1, deleted in Phase 2 |
| `bot/main.py` | 1+2 | Add VectorStore init (Phase 1), graph init (Phase 2) |
| `bot/handlers.py` | 1+2 | Pass vector_store (Phase 1), graph invocation (Phase 2) |
| `agent/state.py` | 2 | New — `BotState` TypedDict |
| `agent/graph.py` | 2 | New — `StateGraph` nodes, edges, compiled graph |
| `models/domain.py` | 2 | Delete `PendingAction` |
