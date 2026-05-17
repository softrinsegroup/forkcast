from collections import defaultdict
import json
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agent.prompts import MEAL_PLAN_PROMPT
from agent.workflows import Workflow
from models import PendingAction, Recipe, ShoppingItem, WeeklyPlan
from storage import RecipeStore, WeeklyPlanStore, ShoppingItemStore
import utils.date


class MealPlanInput(BaseModel):
    recipe_ids: list[int] = Field(description="List of Recipe IDs for a given week")
    notes: str = Field(description="Rationale and any caveats for choosing the recipes")


class MealPlanWorkflow(Workflow):
    def __init__(
        self,
        model: BaseChatModel,
        recipe_store: RecipeStore,
        weekly_plan_store: WeeklyPlanStore,
        shopping_item_store: ShoppingItemStore,
    ):
        self.model = model
        self.recipe_store = recipe_store
        self.weekly_plan_store = weekly_plan_store
        self.shopping_item_store = shopping_item_store

        self.recipe_bank: dict[int, Recipe] = {}
        self.prev_recipe_ids: list[int] = []
        self.new_recipe_ids: list[int] = []
        self.llm_notes: str | None = None
        self.new_weekly_plan: WeeklyPlan | None = None
        self.new_shopping_items: list[ShoppingItem] = []

    async def _fetch_recipe_bank(self) -> None:
        recipe_bank_list = await self.recipe_store.get_all()
        self.recipe_bank = {r.id: r for r in recipe_bank_list}

    async def _fetch_prev_recipe_ids(self) -> None:
        prev_weekly_plan = (
            await self.weekly_plan_store.get_last_weekly_plan_recipe_ids()
        )
        self.prev_recipe_ids = prev_weekly_plan.recipe_ids if prev_weekly_plan else []

    async def _get_recommended_recipes(self) -> None:
        sys_msg = SystemMessage(
            content=MEAL_PLAN_PROMPT,
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
        print("Picked recipe_ids:", resp.recipe_ids)

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
            timestamp=utils.date.this_monday(),
            recipe_ids=self.new_recipe_ids,
            shopping_items=shopping_items,
            created_at=utils.date.today(),
        )

        # Insert WeeklyPlan and ShoppingItems to DB
        await self.weekly_plan_store.create(weekly_plan)
        self.new_weekly_plan = weekly_plan
        self.new_shopping_items = shopping_items

    def _format_message(self) -> str:
        recipe_strs = []
        for idx, recipe_id in enumerate(self.new_recipe_ids):
            recipe = self.recipe_bank[recipe_id]
            recipe_strs.append(f"{idx}. {recipe.name} ({', '.join(recipe.tags)})")
        meal_lines = "\n".join(recipe_strs)

        shopping_strs = []
        for si in self.new_shopping_items:
            shopping_strs.append(f"- {si.ingredient_name} {si.unit} {si.amount}")
        shopping_lines = "\n".join(shopping_strs)

        return (
            f"**Week of {self.new_weekly_plan.timestamp.isoformat()}**\n"
            f"{meal_lines}\n\n"
            f"**Notes**\n"
            f"{self.llm_notes}\n\n"
            f"**Shopping List**\n"
            f"{shopping_lines}"
        )

    async def run(self) -> tuple[str, PendingAction | None]:
        await self._fetch_recipe_bank()
        await self._fetch_prev_recipe_ids()
        await self._get_recommended_recipes()
        await self._persist_weekly_plan()
        return self._format_message(), None
