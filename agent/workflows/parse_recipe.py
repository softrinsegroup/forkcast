from datetime import datetime
import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError

from agent.workflows import Workflow
from models import Recipe, PendingAction
from models.domain import Ingredient
from utils.url import web_fetch


PARSE_RECIPE_PROMPT = """
You are a Meal Planning Assistant. Extract the recipe from the provided page content and return it as structured data.

Extraction rules:
- `name`: the recipe title as written on the page.
- `ingredients`: normalize each ingredient to a single item with a numeric `amount`, a lowercase singular `unit` (e.g. "cup", "tbsp", "g", "clove", "piece"), and a clean `name` (no brand names, no prep notes — move prep
notes like "finely chopped" to the instruction steps). If no unit applies (e.g. "3 eggs"), use `"whole"`.
- `instructions`: one clear action per step as a list of strings. Split multi-action sentences into separate steps.
- `servings`: integer. If not stated, estimate from ingredient quantities (default 4).
- `prep_minutes` / `cook_minutes`: integers. If the page gives a combined time, split it roughly 1/3 prep, 2/3 cook. If not stated, make a reasonable estimate.
- `tags`: assign 2-5 lowercase tags from what the recipe actually is (e.g. "chicken", "pasta", "vegetarian", "quick", "soup", "beef", "seafood", "salad", "breakfast").
"""


class ParseRecipeInput(BaseModel):
    name: str = Field(description="Recipe name")
    ingredients: list[Ingredient] = Field(
        description="List of ingredients needed to make the dish"
    )
    instructions: list[str] = Field(
        description="Step by step instructions to cook the dish"
    )
    servings: int = Field(description="Number of servings")
    prep_minutes: int = Field(description="Number of minutes to prep before cooking")
    cook_minutes: int = Field(description="Number of minutes to cook the dish")
    tags: list[str] = Field(description="Hashtags describing the dish")


class ParseRecipeWorkflow(Workflow):
    def __init__(
        self,
        model: BaseChatModel,
        url: str,
    ):
        self.model = model
        self.url = url

        self.recipe: Recipe | None = None

    async def _parse_url(self) -> None:
        sys_msg = SystemMessage(
            content=PARSE_RECIPE_PROMPT,
            additional_kwargs={"cache_control": {"type": "ephemeral"}},
        )
        page_content = await web_fetch(self.url)
        human_msg = HumanMessage(content=page_content)
        resp = await self.model.with_structured_output(
            ParseRecipeInput, method="json_schema"
        ).ainvoke([sys_msg, human_msg])
        self.recipe = Recipe(
            **resp.model_dump(), created_at=datetime.today(), embedded=False
        )

    def _format_message(self) -> str:
        ingredients = []
        for i in self.recipe.ingredients:
            ingredients.append(f"- {i.name} {i.amount} {i.unit}")
        ingredients_concat = "\n".join(ingredients)

        instructions = []
        for idx, instruction in enumerate(self.recipe.instructions):
            instructions.append(f"{idx + 1}. {instruction}")
        instructions_concat = "\n".join(instructions)

        return (
            f"I've parsed your recipe!\n"
            f"If it looks correct, reply with 'yes' or 'no'.\n\n"
            f"Name: {self.recipe.name}\n"
            f"Tags: {', '.join(self.recipe.tags)}\n"
            f"Prep Mins: {self.recipe.prep_minutes}\n"
            f"Cook Mins: {self.recipe.cook_minutes}\n"
            f"Servings: {self.recipe.servings}\n\n"
            f"Ingredients:\n"
            f"{ingredients_concat}\n\n"
            f"Instructions:\n"
            f"{instructions_concat}\n"
        )

    async def run(self) -> tuple[str, PendingAction | None]:
        try:
            await self._parse_url()
        except ValidationError as e:
            print(f"[ParseRecipeWorkflow] ValidationError: {e}")
            return f"Couldn't parse recipe from {self.url}: {e}", None
        except ValueError as e:
            print(f"[ParseRecipeWorkflow] ValueError: {e}")
            return f"Error with LLM call: {e}", None
        except httpx.ConnectError as e:
            print(f"[ParseRecipeWorkflow] httpx.ConnectError: {e}")
            return f"Error fetching recipe: {e}", None
        except Exception as e:
            print(f"[ParseRecipeWorkflow] Exception: {e}")
            return f"Unexpected error: {e}", None

        return self._format_message(), PendingAction(
            type="confirm_recipe", data={"recipe": self.recipe}
        )
