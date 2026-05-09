from anthropic import AsyncAnthropic

from storage import RecipeStore, IngredientStore


class AddRecipeWorkflow:
    def __init__(
        self,
        client: AsyncAnthropic,
        recipe_store: RecipeStore,
        ingredient_store: IngredientStore,
    ):
        self.client = client
        self.recipe_store = recipe_store
        self.ingredient_store = ingredient_store

    async def run(self) -> str:
        pass
