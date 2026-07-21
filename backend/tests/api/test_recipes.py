from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel

from agent.workflows.parse_recipe import ParseRecipeInput
from api.recipes import router as recipes_router
from storage import RecipeStore
from tests.factories import make_ingredient, make_recipe

INGEST_KEY = "test-ingest-key"


def make_parse_recipe_input(**overrides) -> ParseRecipeInput:
    defaults = dict(
        name="Spaghetti Bolognese",
        ingredients=[make_ingredient(id=1, name="Pasta", unit="g", amount=200.0)],
        instructions=["Boil water", "Cook pasta", "Add sauce"],
        servings=4,
        prep_minutes=10,
        cook_minutes=20,
        tags=["italian", "pasta"],
    )
    defaults.update(overrides)
    return ParseRecipeInput(**defaults)


@pytest.fixture
def mock_model():
    model = MagicMock(spec=BaseChatModel)
    model.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=make_parse_recipe_input()
    )
    return model


@pytest.fixture
def mock_recipe_store():
    store = MagicMock(spec=RecipeStore)
    store.get_id_by_source_url = AsyncMock(return_value=None)
    store.create = AsyncMock(return_value=1)
    return store


@pytest.fixture
def client(mock_model, mock_prompt_store, mock_recipe_store, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", INGEST_KEY)
    app = FastAPI()
    app.include_router(recipes_router)
    app.state.model_agent = mock_model
    app.state.prompt_store = mock_prompt_store
    app.state.recipe_store = mock_recipe_store
    return TestClient(app)


def parse_payload() -> dict:
    return {
        "url": "https://example.com/recipes/pasta",
        "page_text": "Spaghetti Bolognese. Ingredients: pasta. Boil water.",
    }


def ingest_payload() -> dict:
    recipe = make_recipe(source_url="https://example.com/recipes/pasta")
    return recipe.model_dump(mode="json", exclude={"id", "created_at", "embedded"})


def auth(key: str = INGEST_KEY) -> dict:
    return {"Authorization": f"Bearer {key}"}


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------


def test_parse_missing_token_returns_401(client):
    # /parse triggers paid LLM calls — it must sit behind the same ingest key
    # as /ingest, never open.
    resp = client.post("/recipes/parse", json=parse_payload())
    assert resp.status_code == 401


def test_parse_wrong_token_returns_401(client):
    resp = client.post("/recipes/parse", json=parse_payload(), headers=auth("wrong"))
    assert resp.status_code == 401


def test_ingest_unconfigured_key_returns_503(client, monkeypatch):
    # Without INGEST_API_KEY set, the endpoint must be disabled — not open.
    monkeypatch.delenv("INGEST_API_KEY")
    resp = client.post("/recipes/ingest", json=ingest_payload(), headers=auth())
    assert resp.status_code == 503


def test_ingest_missing_token_returns_401(client):
    resp = client.post("/recipes/ingest", json=ingest_payload())
    assert resp.status_code == 401


def test_ingest_wrong_token_returns_401(client):
    resp = client.post(
        "/recipes/ingest", json=ingest_payload(), headers=auth("wrong-key")
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------


def test_parse_valid_page_returns_recipe_with_source_url(client):
    # The scraper forwards this payload verbatim to /recipes/ingest, so it must
    # be a complete RecipeCreate — including source_url, the dedup key, which
    # the LLM never sees and the endpoint must inject from the request URL.
    resp = client.post("/recipes/parse", json=parse_payload(), headers=auth())
    assert resp.status_code == 200
    recipe = resp.json()["recipe"]
    assert recipe["name"] == "Spaghetti Bolognese"
    assert recipe["source_url"] == "https://example.com/recipes/pasta"
    assert recipe["ingredients"][0]["name"] == "Pasta"


def test_parse_invalid_recipe_returns_null(client, mock_model):
    # A page that isn't a recipe must yield {"recipe": null} with 200 — the
    # scraper counts it as no_recipe, not as an error to retry.
    mock_model.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=make_parse_recipe_input(ingredients=[])  # fails validation
    )
    resp = client.post("/recipes/parse", json=parse_payload(), headers=auth())
    assert resp.status_code == 200
    assert resp.json() == {"recipe": None}


def test_parse_llm_failure_returns_502(client, mock_model):
    # LLM/provider errors must surface as 502 so the scraper marks the page
    # failed (retryable) instead of silently treating it as no_recipe.
    mock_model.with_structured_output.return_value.ainvoke = AsyncMock(
        side_effect=ValueError("provider exploded")
    )
    resp = client.post("/recipes/parse", json=parse_payload(), headers=auth())
    assert resp.status_code == 502


def test_parse_missing_page_text_returns_422(client):
    resp = client.post(
        "/recipes/parse", json={"url": "https://example.com"}, headers=auth()
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------


def test_ingest_new_recipe_creates(client, mock_recipe_store):
    resp = client.post("/recipes/ingest", json=ingest_payload(), headers=auth())
    assert resp.status_code == 200
    assert resp.json() == {"id": 1, "created": True}
    mock_recipe_store.create.assert_awaited_once()


def test_ingest_duplicate_source_url_skips(client, mock_recipe_store):
    # Idempotency: re-scraping a site must not duplicate recipes — the endpoint
    # skips URLs it has seen and reports created=False so the CLI counts skips.
    mock_recipe_store.get_id_by_source_url = AsyncMock(return_value=42)
    resp = client.post("/recipes/ingest", json=ingest_payload(), headers=auth())
    assert resp.status_code == 200
    assert resp.json() == {"id": 42, "created": False}
    mock_recipe_store.create.assert_not_awaited()


def test_ingest_concurrent_duplicate_still_returns_200(client, mock_recipe_store):
    # The lookup above is check-then-act: a second writer can slip past it and
    # lose to the unique index. The scraper marks a page 'failed' on any non-200,
    # so a race must still read back as a skip — never a 500 that costs a recipe.
    mock_recipe_store.get_id_by_source_url = AsyncMock(side_effect=[None, 42])
    mock_recipe_store.create = AsyncMock(side_effect=asyncpg.UniqueViolationError())

    resp = client.post("/recipes/ingest", json=ingest_payload(), headers=auth())

    assert resp.status_code == 200
    assert resp.json() == {"id": 42, "created": False}


def test_ingest_unique_violation_without_row_propagates(client, mock_recipe_store):
    # A UniqueViolationError with no matching source_url is a different constraint
    # failing. Swallowing it would report a phantom skip and silently drop data.
    mock_recipe_store.get_id_by_source_url = AsyncMock(return_value=None)
    mock_recipe_store.create = AsyncMock(side_effect=asyncpg.UniqueViolationError())

    with pytest.raises(asyncpg.UniqueViolationError):
        client.post("/recipes/ingest", json=ingest_payload(), headers=auth())


def test_ingest_missing_source_url_returns_422(client):
    # source_url is the dedup key; a payload without it must be rejected by
    # validation, never stored.
    payload = ingest_payload()
    del payload["source_url"]
    resp = client.post("/recipes/ingest", json=payload, headers=auth())
    assert resp.status_code == 422
