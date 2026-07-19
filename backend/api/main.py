import asyncio
from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from langchain_anthropic import ChatAnthropic
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langfuse import get_client as get_langfuse_client
import structlog

from logging_config import configure_logging
from agent import create_graph
from storage import (
    PromptStore,
    RecipeStore,
    ShoppingItemStore,
    UserStore,
    WaitlistStore,
    WeeklyPlanStore,
    init_db,
    init_vector_store,
    reconcile_recipes,
)
from api.auth import router as auth_router
from api.users import router as users_router
from api.waitlist import router as waitlist_router
from api.chat import router as chat_router
from api.meal_plans import router as meal_plans_router
from api.recipes import router as recipes_router
from api.middleware import RequestLoggingMiddleware

# Configure unified logging before the app (and Uvicorn) start emitting logs.
configure_logging()

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB
    db_pool = await init_db()
    recipe_store = RecipeStore(db_pool)
    weekly_plan_store = WeeklyPlanStore(db_pool)
    shopping_item_store = ShoppingItemStore(db_pool)
    prompt_store = PromptStore(db_pool)
    user_store = UserStore(db_pool)
    waitlist_store = WaitlistStore(db_pool)
    log.info("startup", step="database")

    # Init Vector DB
    vector_store = await init_vector_store()
    log.info("startup", step="vector_database")

    # LangGraph checkpointer
    async with AsyncPostgresSaver.from_conn_string(
        os.getenv("DATABASE_URL")
    ) as checkpointer:
        await checkpointer.setup()

        # Init LangFuse
        langfuse = get_langfuse_client()
        if langfuse.auth_check():
            log.info("startup", step="langfuse", authenticated=True)
            langfuse_handler = CallbackHandler()
        else:
            log.warning("startup", step="langfuse", authenticated=False)
            langfuse_handler = None

        # Init Anthropic client
        model_agent = ChatAnthropic(model="claude-sonnet-4-6")
        log.info("startup", step="anthropic")

        # Create Graph
        graph = create_graph(
            model_agent=model_agent,
            recipe_store=recipe_store,
            weekly_plan_store=weekly_plan_store,
            shopping_item_store=shopping_item_store,
            prompt_store=prompt_store,
            vector_store=vector_store,
            checkpointer=checkpointer,
            langfuse_handler=langfuse_handler,
        )

        # Store on app.state so routers can access via request.app.state
        app.state.model_agent = model_agent
        app.state.recipe_store = recipe_store
        app.state.weekly_plan_store = weekly_plan_store
        app.state.shopping_item_store = shopping_item_store
        app.state.prompt_store = prompt_store
        app.state.user_store = user_store
        app.state.waitlist_store = waitlist_store
        app.state.vector_store = vector_store
        app.state.graph = graph

        # Create background tasks
        reconcile_task = asyncio.create_task(
            _reconcile_recipes_loop(recipe_store, vector_store)
        )

        yield

        # Cancel background tasks
        reconcile_task.cancel()

    # On app shutdown
    await db_pool.close()


async def _reconcile_recipes_loop(recipe_store, vector_store):
    while True:
        await reconcile_recipes(recipe_store, vector_store)
        await asyncio.sleep(300)


app = FastAPI(lifespan=lifespan)

# Add middleware
# https_only in production so the session cookie is Secure; the app calls the API
# cross-origin (app.forkcast.app -> api.forkcast.app), same site, so Lax suffices.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY"),
    https_only=os.getenv("ENVIRONMENT", "development") == "production",
)
# Added last so it wraps SessionMiddleware and is the outermost layer, binding
# request context before anything else runs.
app.add_middleware(RequestLoggingMiddleware)
# CORS added after RequestLoggingMiddleware so it is outermost and answers the
# cross-origin preflight (OPTIONS) before anything else runs. Serves both the
# landing page's waitlist POST and the app's credentialed API calls. Origins are
# comma-separated in CORS_ALLOW_ORIGINS (landing + app.forkcast.app).
# allow_credentials=True requires explicit origins (no wildcard).
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS").split(","),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
    allow_credentials=True,
)

# Include routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(waitlist_router)
app.include_router(chat_router)
app.include_router(meal_plans_router)
app.include_router(recipes_router)


@app.get("/healthcheck")
async def healthcheck():
    return {"status": "ok"}
