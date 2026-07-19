import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError
import structlog

from models import Ingredient, PromptType, RecipeCreate
from storage import PromptStore
from utils import web_fetch, backup_web_fetch

log = structlog.get_logger()

# Tag applied to the structured-output LLM call so the chat stream can filter
# out its raw-JSON tokens (see api/chat.py). The parsed recipe is delivered as a
# dedicated "recipe" SSE event instead.
RECIPE_PARSE_TAG = "recipe_parse"


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


async def parse_page_text(
    model: BaseChatModel,
    prompt_store: PromptStore,
    url: str,
    page_text: str,
) -> RecipeCreate | None:
    """
    Parse recipe page text with the LLM; None if it doesn't validate.

    Shared core of the chat workflow below and POST /recipes/parse — the
    single place the PARSE_RECIPE prompt and structured-output schema are used.
    """
    prompt = await prompt_store.get(PromptType.PARSE_RECIPE)
    sys_msg = SystemMessage(
        content=prompt.prompt,
        additional_kwargs={"cache_control": {"type": "ephemeral"}},
    )
    human_msg = HumanMessage(content=page_text)
    recipe_input = await model.with_structured_output(
        ParseRecipeInput, method="json_schema"
    ).ainvoke([sys_msg, human_msg], config={"tags": [RECIPE_PARSE_TAG]})

    if not _validate_recipe(recipe_input):
        return None
    return RecipeCreate(**recipe_input.model_dump(), source_url=url)


def _validate_recipe(recipe: ParseRecipeInput) -> bool:
    if recipe.ingredients == []:
        return False
    if recipe.instructions == []:
        return False
    if "error" in recipe.instructions[0]:
        return False
    if recipe.tags == []:
        return False
    if recipe.tags[0] == "unknown":
        return False
    if recipe.servings == 0:
        return False
    if recipe.prep_minutes == 0:
        return False
    if recipe.cook_minutes == 0:
        return False
    return True


class ParseRecipeWorkflow:
    def __init__(
        self,
        model: BaseChatModel,
        url: str,
        prompt_store: PromptStore,
    ):
        self.model = model
        self.url = url
        self.prompt_store = prompt_store

        self.recipe: RecipeCreate | None = None

    async def _parse_page_content(self, page_content: str) -> None:
        self.recipe = await parse_page_text(
            self.model, self.prompt_store, self.url, page_content
        )

    def _format_message(self) -> list[str]:
        ingredients = []
        for i in self.recipe.ingredients:
            ingredients.append(f"- {i.name} {i.amount} {i.unit}")
        ingredients_concat = "\n".join(ingredients)

        instructions = []
        for idx, instruction in enumerate(self.recipe.instructions):
            instructions.append(f"{idx + 1}. {instruction}")
        instructions_concat = "\n".join(instructions)

        msgs = []
        msgs.append(
            f"I've parsed your recipe! ✅\n\n"
            f"Name: {self.recipe.name}\n"
            f"Tags: {', '.join(self.recipe.tags)}\n"
            f"Prep Mins: {self.recipe.prep_minutes}\n"
            f"Cook Mins: {self.recipe.cook_minutes}\n"
            f"Servings: {self.recipe.servings}"
        )
        msgs.append(f"Ingredients:\n{ingredients_concat}")
        msgs.append(f"Instructions:\n{instructions_concat}")

        return msgs

    async def run(self) -> tuple[list[str], RecipeCreate | None]:
        try:
            # Try primary web fetch
            log.info("recipe_fetch", source="primary", url=self.url)
            page_content = await web_fetch(self.url)
            await self._parse_page_content(page_content)

            # Use secondary web fetch if unable to parse
            if not self.recipe:
                log.info("recipe_fetch", source="secondary", url=self.url)
                page_content = await backup_web_fetch(self.url)
                await self._parse_page_content(page_content)

            # Raise error if both web fetches failed
            if not self.recipe:
                raise ValidationError("Primary/secondary web fetch failed.")
        except ValidationError as e:
            log.warning(
                "recipe_parse_failed", reason="validation", url=self.url, error=str(e)
            )
            return f"Couldn't parse recipe from {self.url}: {e}", None
        except ValueError as e:
            log.warning(
                "recipe_parse_failed", reason="llm_call", url=self.url, error=str(e)
            )
            return f"Error with LLM call: {e}", None
        except httpx.ConnectError as e:
            log.warning(
                "recipe_parse_failed", reason="connect", url=self.url, error=str(e)
            )
            return f"Error fetching recipe: {e}", None
        except Exception as e:
            log.exception("recipe_parse_failed", reason="unexpected", url=self.url)
            return f"Unexpected error: {e}", None

        return self._format_message(), self.recipe
