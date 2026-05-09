from datetime import datetime
from anthropic import AsyncAnthropic

from agent.prompts import PARSE_RECIPE_PROMPT
from agent.tools import PARSE_RECIPE_TOOL
from models import Ingredient, Recipe
from storage import RecipeStore, IngredientStore


class ParseRecipeWorkflow:
    def __init__(
        self,
        client: AsyncAnthropic,
        recipe_store: RecipeStore,
        ingredient_store: IngredientStore,
        url: str,
    ):
        self.client = client
        self.recipe_store = recipe_store
        self.ingredient_store = ingredient_store
        self.url = url

        self.recipe: Recipe | None = None

    async def _parse_url(self) -> None:
        # Run loop until both tools are called
        messages = [
            {
                "role": "user",
                "content": self.url,
            }
        ]
        while True:
            resp = await self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=[
                    {
                        "type": "text",
                        "text": PARSE_RECIPE_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=[
                    {"type": "web_fetch_20260209", "name": "web_fetch"},
                    PARSE_RECIPE_TOOL,
                ],
                tool_choice={"type": "auto"},
                messages=messages,
            )
            if resp.stop_reason == "tool_use":
                # Claude called tool "parse_recipe"
                break
            elif resp.stop_reason == " pause_turn":
                # Append web_fetch call + result
                # Send it back to Claude to "parse_recipe"
                messages.append({"role": "assistant", "content": resp.content})
            else:
                raise ValueError(f"Unexpected stop_reason: {resp.stop_reason}")

        # Parse outputs
        input = resp.content[0].input
        recipe = Recipe(
            name=input["name"],
            instructions=input["instructions"],
            ingredients=[
                Ingredient(name=i["name"], amount=i["amount"], unit=i["unit"])
                for i in input["ingredients"]
            ],
            servings=input["servings"],
            prep_minutes=input["prep_minutes"],
            cook_minutes=input["cook_minutes"],
            tags=input["tags"],
            created_at=datetime.today(),
        )

        # Validate all fields present
        for key, val in recipe.items():
            if val is None:
                raise ValueError(f"Parsed recipe could not find: {key}")

        self.recipe = recipe

    def _format_message(self) -> str:
        ingredients = []
        for i in self.recipe.ingredients:
            ingredients.append(f"- {i.name} {i.amount} {i.unit}")
        ingredient_lines = "\n".join(ingredients)

        instruction_lines = []
        for idx, instruction in enumerate(self.recipe.instructions):
            instruction_lines.append(f"{idx + 1}. {instruction}\n")

        return (
            f"I've parsed your recipe. If it looks correct, reply with 'yes' or 'no'.\n"
            f"Name: {self.recipe.name}\n"
            f"Tags: {self.recipe.tags}\n"
            f"Prep Mins: {self.recipe.prep_minutes}\n"
            f"Cook Mins: {self.recipe.cook_minutes}\n"
            f"Servings: {self.recipe.servings}\n\n"
            f"Ingredients:\n"
            f"{ingredient_lines}\n\n"
            f"Instructions:\n"
            f"{instruction_lines}\n\n"
        )

    async def run(self) -> tuple[str, Recipe | None]:
        try:
            await self._parse_url()
        except ValueError:
            return f"Couldn't parse recipe from {self.url}", None

        return self._format_message(), self.recipe
