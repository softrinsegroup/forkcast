from unittest.mock import AsyncMock

import pytest
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from models import Ingredient
from storage.recipe_store import RecipeStore
from storage.vector_store import _build_recipe_document, embed_recipe, reconcile_recipes
from tests.factories import make_recipe

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_vector_store():
    vs = AsyncMock(spec=VectorStore)
    vs.aadd_documents = AsyncMock(return_value=["doc-id-1"])
    return vs


@pytest.fixture
def mock_recipe_store():
    return AsyncMock(spec=RecipeStore)


# ---------------------------------------------------------------------------
# _build_recipe_document
# ---------------------------------------------------------------------------


def test_build_recipe_document_content():
    recipe = make_recipe(
        id=1,
        name="Chicken Rice",
        tags=["easy", "healthy"],
        ingredients=[
            Ingredient(id=1, name="Chicken", unit="g", amount=450),
            Ingredient(id=2, name="Rice", unit="cup", amount=2),
        ],
        prep_minutes=10,
        cook_minutes=20,
    )
    doc = _build_recipe_document(recipe)
    assert "Chicken Rice" in doc.page_content
    assert "Tags: easy, healthy" in doc.page_content
    assert "Ingredients: Chicken, Rice" in doc.page_content
    assert "Ready in 30 minutes" in doc.page_content


def test_build_recipe_document_metadata():
    recipe = make_recipe()
    recipe.id = 42
    doc = _build_recipe_document(recipe)
    assert doc.metadata["recipe_id"] == 42


def test_build_recipe_document_no_tags_no_ingredients():
    recipe = make_recipe(tags=[], ingredients=[])
    doc = _build_recipe_document(recipe)
    assert isinstance(doc, Document)
    assert "Tags: \n" in doc.page_content
    assert "Ingredients: \n" in doc.page_content


def test_build_recipe_document_time_sum():
    recipe = make_recipe(prep_minutes=15, cook_minutes=25)
    doc = _build_recipe_document(recipe)
    assert "Ready in 40 minutes" in doc.page_content


# ---------------------------------------------------------------------------
# embed_recipe
# ---------------------------------------------------------------------------


async def test_embed_recipe_calls_aadd_documents(mock_vector_store):
    recipe = make_recipe()
    await embed_recipe(mock_vector_store, recipe)
    mock_vector_store.aadd_documents.assert_called_once()
    (docs,), _ = mock_vector_store.aadd_documents.call_args
    assert len(docs) == 1
    assert isinstance(docs[0], Document)


async def test_embed_recipe_document_has_correct_metadata(mock_vector_store):
    recipe = make_recipe()
    recipe.id = 7
    await embed_recipe(mock_vector_store, recipe)
    (docs,), _ = mock_vector_store.aadd_documents.call_args
    assert docs[0].metadata["recipe_id"] == 7


async def test_embed_recipe_propagates_exception(mock_vector_store):
    mock_vector_store.aadd_documents.side_effect = RuntimeError("connection refused")
    with pytest.raises(RuntimeError, match="connection refused"):
        await embed_recipe(mock_vector_store, make_recipe())


# ---------------------------------------------------------------------------
# reconcile_recipes
# ---------------------------------------------------------------------------


async def test_reconcile_no_unembedded_recipes(mock_recipe_store, mock_vector_store):
    mock_recipe_store.get_all_unembedded.return_value = []
    await reconcile_recipes(mock_recipe_store, mock_vector_store)
    mock_vector_store.aadd_documents.assert_not_called()
    mock_recipe_store.update_embedded.assert_not_called()


async def test_reconcile_all_succeed(mock_recipe_store, mock_vector_store):
    r1 = make_recipe(name="A")
    r1.id = 1
    r2 = make_recipe(name="B")
    r2.id = 2
    mock_recipe_store.get_all_unembedded.return_value = [r1, r2]

    await reconcile_recipes(mock_recipe_store, mock_vector_store)

    assert mock_vector_store.aadd_documents.call_count == 2
    mock_recipe_store.update_embedded.assert_called_once_with([1, 2])


async def test_reconcile_partial_failure(mock_recipe_store, mock_vector_store):
    r1 = make_recipe(name="A")
    r1.id = 1
    r2 = make_recipe(name="B")
    r2.id = 2
    r3 = make_recipe(name="C")
    r3.id = 3
    mock_recipe_store.get_all_unembedded.return_value = [r1, r2, r3]
    mock_vector_store.aadd_documents.side_effect = [
        ["doc-1"],
        RuntimeError("embed failed"),
        ["doc-3"],
    ]

    await reconcile_recipes(mock_recipe_store, mock_vector_store)

    mock_recipe_store.update_embedded.assert_called_once_with([1, 3])


async def test_reconcile_all_fail(mock_recipe_store, mock_vector_store):
    r1 = make_recipe(name="A")
    r1.id = 1
    mock_recipe_store.get_all_unembedded.return_value = [r1]
    mock_vector_store.aadd_documents.side_effect = RuntimeError("down")

    await reconcile_recipes(mock_recipe_store, mock_vector_store)

    mock_recipe_store.update_embedded.assert_not_called()


async def test_reconcile_uses_real_recipe_store(db, mock_vector_store):
    store = RecipeStore(db)
    await store.create(make_recipe(name="A"))
    await store.create(make_recipe(name="B"))
    assert len(await store.get_all_unembedded()) == 2

    await reconcile_recipes(store, mock_vector_store)

    assert await store.get_all_unembedded() == []
