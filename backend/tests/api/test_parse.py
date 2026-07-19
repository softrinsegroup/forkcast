from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel

from agent.workflows.parse_recipe import ParseRecipeInput
from api.recipes import router as recipes_router
from tests.factories import make_ingredient

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
def client(mock_model, mock_prompt_store, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", INGEST_KEY)
    app = FastAPI()
    app.include_router(recipes_router)
    app.state.model_agent = mock_model
    app.state.prompt_store = mock_prompt_store
    return TestClient(app)


def parse_payload() -> dict:
    return {
        "url": "https://example.com/recipes/pasta",
        "page_text": "Spaghetti Bolognese. Ingredients: pasta. Boil water.",
    }


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
