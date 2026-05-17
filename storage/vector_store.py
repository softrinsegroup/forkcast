from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from models.domain import Recipe


async def embed_recipe(vector_store: VectorStore, recipe: Recipe) -> None:
    doc = _build_recipe_document(recipe)
    ids = await vector_store.aadd_documents([doc])
    print(f"Embedded recipe_id {recipe.id} - document_ids {ids}")


def _build_recipe_document(recipe: Recipe) -> str:
    lines = [recipe.name]
    lines.append(f"Tags: {', '.join(recipe.tags)}")
    lines.append(f"Ingredients: {', '.join(i.name for i in recipe.ingredients)}")
    lines.append(f"Ready in {recipe.prep_minutes + recipe.cook_minutes} minutes")
    return Document(page_content="\n".join(lines), metadata={"recipe_id": recipe.id})
