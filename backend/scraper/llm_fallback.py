import os
from pathlib import Path

from bs4 import BeautifulSoup
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from agent.workflows.parse_recipe import ParseRecipeInput
from models import RecipeCreate

# Read from the seed file, not PromptStore — the scraper never touches Postgres.
_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "parse_recipe_v1.txt"

_INSTRUCTION_WORDS = ("instruction", "direction", "method")


def _looks_like_recipe(text: str) -> bool:
    """Cheap deterministic pre-filter so we only spend tokens on likely hits."""
    lowered = text.lower()
    return "ingredient" in lowered and any(w in lowered for w in _INSTRUCTION_WORDS)


class LlmFallback:
    """
    LLM extraction for recipe pages without usable JSON-LD.

    Capped: opt-in via --llm-fallback and hard-limited to `cap` calls per run
    so a large crawl can't silently burn through the token budget.
    """

    def __init__(self, cap: int):
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("--llm-fallback requires ANTHROPIC_API_KEY to be set")
        self.model = ChatAnthropic(model="claude-sonnet-4-6")
        self.system_prompt = _PROMPT_PATH.read_text()
        self.remaining = cap

    async def try_parse(self, html: str, source_url: str) -> RecipeCreate | None:
        page_text = BeautifulSoup(html, "html.parser").get_text()
        if self.remaining <= 0 or not _looks_like_recipe(page_text):
            return None
        self.remaining -= 1

        sys_msg = SystemMessage(
            content=self.system_prompt,
            additional_kwargs={"cache_control": {"type": "ephemeral"}},
        )
        try:
            parsed = await self.model.with_structured_output(
                ParseRecipeInput, method="json_schema"
            ).ainvoke([sys_msg, HumanMessage(content=page_text)])
        except Exception as e:
            print(f"  llm fallback error: {e}")
            return None

        # Same quality gate as the JSON-LD path (extract._node_to_recipe).
        if not parsed.name or not parsed.ingredients or not parsed.instructions:
            return None

        return RecipeCreate(**parsed.model_dump(), source_url=source_url)
