import asyncio
from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
from langchain_anthropic import ChatAnthropic
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langfuse import get_client as get_langfuse_client
from starlette.staticfiles import StaticFiles

from agent import create_graph
from storage import (
    PromptStore,
    RecipeStore,
    ShoppingItemStore,
    UserStore,
    WeeklyPlanStore,
    init_db,
    init_vector_store,
    reconcile_recipes,
)
from api.auth import router as auth_router
from api.users import router as users_router
from api.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB
    db_pool = await init_db()
    recipe_store = RecipeStore(db_pool)
    weekly_plan_store = WeeklyPlanStore(db_pool)
    shopping_item_store = ShoppingItemStore(db_pool)
    prompt_store = PromptStore(db_pool)
    user_store = UserStore(db_pool)
    print("Initialized database")

    # Init Vector DB
    vector_store = await init_vector_store()
    print("Initialized vector database")

    # LangGraph checkpointer
    async with AsyncPostgresSaver.from_conn_string(
        os.getenv("DATABASE_URL")
    ) as checkpointer:
        await checkpointer.setup()

        # Init LangFuse
        langfuse = get_langfuse_client()
        if langfuse.auth_check():
            print("Initialized and authenticated LangFuse client")
            langfuse_handler = CallbackHandler()
        else:
            print("LangFuse authentication failed. Check your credentials and host.")
            langfuse_handler = None

        # Init Anthropic client
        model_agent = ChatAnthropic(model="claude-sonnet-4-6")
        print("Initialized Anthropic clients")

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
        app.state.recipe_store = recipe_store
        app.state.weekly_plan_store = weekly_plan_store
        app.state.shopping_item_store = shopping_item_store
        app.state.prompt_store = prompt_store
        app.state.user_store = user_store
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
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY"))
# app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(chat_router)


@app.get("/healthcheck")
async def healthcheck():
    return {"status": "ok"}


# MUST BE LAST ROUTE!
# Serves the React static page.
# @app.get("/{full_path:path}")
# async def spa_fallback():
#     return FileResponse("frontend/dist/index.html")
