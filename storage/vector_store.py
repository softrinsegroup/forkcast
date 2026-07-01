import os
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from langchain_voyageai import VoyageAIEmbeddings
from langchain_postgres import PGEngine, PGVectorStore

from models.domain import Recipe
from storage.recipe_store import RecipeStore

TABLE_NAME = "recipe_embeddings"
VECTOR_SIZE = 1024


async def init_vector_store() -> VectorStore:
    """Initializes embeddings and the vector store"""
    # Init embeddings
    embeddings = VoyageAIEmbeddings(
        voyage_api_key=os.getenv("VOYAGE_API_KEY"),
        model="voyage-4",
    )
    print("Initialized embeddings")

    # Init table
    pg_engine = PGEngine.from_connection_string(url=os.getenv("ASYNC_DATABASE_URL"))
    await pg_engine.ainit_vectorstore_table(
        table_name=TABLE_NAME,
        vector_size=VECTOR_SIZE,
    )
    print("Initialized PGEngine + table")

    # Init vector store
    store = await PGVectorStore.create(
        engine=pg_engine,
        table_name=TABLE_NAME,
        embedding_service=embeddings,
    )
    print("Initialized PGVectorStore")

    return store


async def reconcile_recipes(recipe_store: RecipeStore, vector_store: VectorStore):
    # Fetch all unembedded Recipes
    recipes = await recipe_store.get_all_unembedded()
    print(f"Reconciling {len(recipes)} unembedded Recipe(s)...")

    # Embed each unembedded Recipe and track ids
    embedded_ids = []
    for recipe in recipes:
        try:
            await embed_recipe(vector_store, recipe)
            embedded_ids.append(recipe.id)
        except Exception as e:
            print(f"Warning: failed to embed recipe_id={recipe.id}: {e}")

    # Update DB flags
    if embedded_ids:
        await recipe_store.update_embedded(embedded_ids)


async def embed_recipe(vector_store: VectorStore, recipe: Recipe) -> None:
    doc = _build_recipe_document(recipe)
    ids = await vector_store.aadd_documents([doc])
    print(f"Embedded recipe_id {recipe.id} => document_ids {ids}")


def _build_recipe_document(recipe: Recipe) -> Document:
    lines = [recipe.name]
    lines.append(f"Tags: {', '.join(recipe.tags)}")
    lines.append(f"Ingredients: {', '.join(i.name for i in recipe.ingredients)}")
    lines.append(f"Ready in {recipe.prep_minutes + recipe.cook_minutes} minutes")
    return Document(page_content="\n".join(lines), metadata={"recipe_id": recipe.id})
