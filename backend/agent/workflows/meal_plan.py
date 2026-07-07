from collections import defaultdict
import json
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.vectorstores import VectorStore
from pydantic import BaseModel, Field
import structlog

from models import Recipe, ShoppingItem, WeeklyPlan, PromptType
from storage import PromptStore, RecipeStore, WeeklyPlanStore, ShoppingItemStore
import utils.date

log = structlog.get_logger()


class MealPlanInput(BaseModel):
    recipe_ids: list[int] = Field(description="List of Recipe IDs for a given week")
    notes: str = Field(description="Rationale and any caveats for choosing the recipes")


class MealPlanWorkflow:
    def __init__(
        self,
        user_id: str,
        model: BaseChatModel,
        recipe_store: RecipeStore,
        weekly_plan_store: WeeklyPlanStore,
        shopping_item_store: ShoppingItemStore,
        prompt_store: PromptStore,
        vector_store: VectorStore,
    ):
        self.user_id = user_id
        self.model = model
        self.recipe_store = recipe_store
        self.weekly_plan_store = weekly_plan_store
        self.shopping_item_store = shopping_item_store
        self.prompt_store = prompt_store
        self.vector_store = vector_store

        self.recipe_bank: dict[int, Recipe] = {}
        self.prev_recipe_ids: list[int] = []
        self.new_recipe_ids: list[int] = []
        self.llm_notes: str | None = None
        self.new_weekly_plan: WeeklyPlan | None = None
        self.new_shopping_items: list[ShoppingItem] = []

    async def _fetch_prev_recipe_ids(self) -> None:
        prev_weekly_plan = await self.weekly_plan_store.get_last_weekly_plan_recipe_ids(
            self.user_id
        )
        self.prev_recipe_ids = prev_weekly_plan.recipe_ids if prev_weekly_plan else []

    async def _build_recipe_bank(self, user_input: str) -> None:
        # Fetch short list of recipes from vector store
        docs = await self.vector_store.asimilarity_search(user_input, k=10)
        candidate_ids = {int(d.metadata["recipe_id"]) for d in docs}

        all_ids = list(candidate_ids | set(self.prev_recipe_ids))

        recipes = await self.recipe_store.get_by_ids(all_ids)
        self.recipe_bank = {r.id: r for r in recipes}

    async def _get_recommended_recipes(self) -> None:
        prompt = await self.prompt_store.get(PromptType.PLAN)
        sys_msg = SystemMessage(
            content=prompt.prompt,
            additional_kwargs={"cache_control": {"type": "ephemeral"}},
        )
        recipe_bank_short = {
            rid: {"name": r.name, "tags": r.tags} for rid, r in self.recipe_bank.items()
        }
        human_msg = HumanMessage(
            content=(
                f"Recipe bank:\n{json.dumps(recipe_bank_short)}\n\n"
                f"Previous recipe_ids: {json.dumps(self.prev_recipe_ids)}"
            )
        )
        resp: MealPlanInput = (
            await self.model.bind(max_tokens=512)
            .with_structured_output(MealPlanInput, method="json_schema")
            .ainvoke(
                [
                    sys_msg,
                    human_msg,
                ]
            )
        )
        log.info("meal_plan_recipes_picked", recipe_ids=resp.recipe_ids)

        # Raise exception if picked a non-existent recipe_id
        missing_recipe_ids = [
            rid
            for rid in resp.recipe_ids
            if rid is not None and rid not in self.recipe_bank
        ]
        if missing_recipe_ids:
            raise ValueError(f"Could not find recipe_ids: {missing_recipe_ids}")

        self.new_recipe_ids = resp.recipe_ids
        self.llm_notes = resp.notes

    async def _persist_weekly_plan(self) -> None:
        # Aggregate ingredients
        agg_ingredients = defaultdict(float)
        for recipe_id in self.new_recipe_ids:
            recipe = self.recipe_bank[recipe_id]
            for ing in recipe.ingredients:
                key = (ing.name, ing.unit)
                agg_ingredients[key] += ing.amount

        # Create shopping_items
        shopping_items = []
        for key, amount in agg_ingredients.items():
            name, unit = key
            shopping_item = ShoppingItem(
                ingredient_name=name,
                unit=unit,
                amount=amount,
            )
            shopping_items.append(shopping_item)

        # Create weekly_plan
        weekly_plan = WeeklyPlan(
            user_id=self.user_id,
            timestamp=utils.date.this_monday(),
            recipe_ids=self.new_recipe_ids,
            shopping_items=shopping_items,
            created_at=utils.date.today(),
        )

        # Insert WeeklyPlan and ShoppingItems to DB
        await self.weekly_plan_store.create(weekly_plan)
        self.new_weekly_plan = weekly_plan
        self.new_shopping_items = shopping_items

    def _format_message(self) -> list[str]:
        recipe_strs = []
        for idx, recipe_id in enumerate(self.new_recipe_ids):
            recipe = self.recipe_bank[recipe_id]
            recipe_strs.append(f"{idx + 1}. {recipe.name} ({', '.join(recipe.tags)})")
        meal_lines = "\n".join(recipe_strs)

        shopping_strs = []
        for si in self.new_shopping_items:
            shopping_strs.append(f"- {si.ingredient_name} {si.unit} {si.amount}")
        shopping_lines = "\n".join(shopping_strs)

        # Separate messages for recipes, notes, and shopping list
        msgs = []
        msgs.append(
            f"**Week of {self.new_weekly_plan.timestamp.isoformat()}**\n{meal_lines}"
        )
        msgs.append(f"**Notes**\n{self.llm_notes}")
        msgs.append(f"**Shopping List**\n{shopping_lines}")

        return msgs

    async def run(self, user_input: str) -> list[str]:
        await self._fetch_prev_recipe_ids()
        await self._build_recipe_bank(user_input)
        await self._get_recommended_recipes()
        await self._persist_weekly_plan()
        return self._format_message()
