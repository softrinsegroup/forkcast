from datetime import datetime
from anthropic import AsyncAnthropic
from pydantic import ValidationError

from agent.prompts import PARSE_RECIPE_PROMPT
from agent.tools import PARSE_RECIPE_TOOL
from agent.workflows import Workflow
from models import Recipe, PendingAction


class ParseRecipeWorkflow(Workflow):
    def __init__(
        self,
        client: AsyncAnthropic,
        url: str,
    ):
        self.client = client
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
            elif resp.stop_reason == "pause_turn":
                # Append web_fetch call + result
                # Send it back to Claude to "parse_recipe"
                messages.append({"role": "assistant", "content": resp.content})
            else:
                raise ValueError(f"Unexpected stop_reason: {resp.stop_reason}")

        # Parse outputs
        tool_block = next(b for b in resp.content if b.type == "tool_use")
        tool_input = tool_block.input
        try:
            recipe = Recipe.model_validate(
                {**tool_input, "created_at": datetime.today()}
            )
            self.recipe = recipe
        except ValidationError as e:
            print(f"Error parsing Recipe: {e.errors()[0]['msg']}")
            raise

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
            f"I've parsed your recipe. If it looks correct, reply with 'yes' or 'no'.\n\n"
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
        except ValidationError:
            return f"Couldn't parse recipe from {self.url}", None
        except ValueError as e:
            return f"Error with LLM call: {e}", None

        return self._format_message(), PendingAction(
            type="confirm_recipe", data={"recipe": self.recipe}
        )
