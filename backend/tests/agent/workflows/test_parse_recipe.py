import httpx
from langchain_core.language_models import BaseChatModel
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from agent.workflows.parse_recipe import ParseRecipeInput, ParseRecipeWorkflow
from models.domain import Ingredient
from tests.factories import make_ingredient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_model(response: ParseRecipeInput) -> MagicMock:
    model = MagicMock(spec=BaseChatModel)
    model.with_structured_output.return_value.ainvoke = AsyncMock(return_value=response)
    return model


def make_parse_recipe_input(**overrides) -> ParseRecipeInput:
    defaults = dict(
        name="Spaghetti Bolognese",
        ingredients=[make_ingredient(id=1, name="Pasta", unit="g", amount=200.0)],
        instructions=["Boil water", "Cook pasta", "Add sauce"],
        servings=4,
        prep_minutes=10,
        cook_minutes=20,
        tags=["italian", "pasta"],
    )
    defaults.update(overrides)
    return ParseRecipeInput(**defaults)


def make_validation_error() -> ValidationError:
    try:
        ParseRecipeInput()  # all fields required → always raises
    except ValidationError as e:
        return e


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workflow_with_recipe(mock_prompt_store):
    wf = ParseRecipeWorkflow(
        MagicMock(spec=BaseChatModel), "https://example.com/recipe", mock_prompt_store
    )
    from datetime import datetime
    from models.domain import Recipe

    wf.recipe = Recipe(
        id=1,
        name="Chicken Soup",
        ingredients=[
            Ingredient(id=1, name="Chicken", unit="g", amount=300.0),
            Ingredient(id=2, name="Carrot", unit="piece", amount=2.0),
        ],
        instructions=["Chop vegetables", "Simmer chicken", "Season to taste"],
        servings=4,
        prep_minutes=15,
        cook_minutes=45,
        tags=["soup", "chicken"],
        created_at=datetime.today(),
        embedded=False,
    )
    return wf


# ---------------------------------------------------------------------------
# _parse_page_content
# ---------------------------------------------------------------------------


async def test_parse_page_content_parses_recipe(mock_prompt_store):
    # New recipes must start embedded=False
    wf = ParseRecipeWorkflow(
        make_mock_model(make_parse_recipe_input()),
        "https://example.com/recipe",
        mock_prompt_store,
    )
    await wf._parse_page_content("page content")
    assert wf.recipe.name == "Spaghetti Bolognese"
    assert wf.recipe.ingredients[0].name == "Pasta"
    assert wf.recipe.instructions == ["Boil water", "Cook pasta", "Add sauce"]
    assert wf.recipe.servings == 4
    assert wf.recipe.prep_minutes == 10
    assert wf.recipe.cook_minutes == 20
    assert wf.recipe.tags == ["italian", "pasta"]


# ---------------------------------------------------------------------------
# _format_message
# ---------------------------------------------------------------------------


def test_format_message_returns_three_parts(workflow_with_recipe):
    # Bot sends each part as a separate Telegram message — the count must be exactly 3
    msgs = workflow_with_recipe._format_message()
    assert len(msgs) == 3


def test_format_message_first_part_contains_recipe_metadata(workflow_with_recipe):
    # First message is the recipe summary card: name, tags, prep/cook minutes, servings
    msg = workflow_with_recipe._format_message()[0]
    assert "Chicken Soup" in msg
    assert "soup" in msg
    assert "chicken" in msg
    assert "15" in msg
    assert "45" in msg
    assert "4" in msg


def test_format_message_second_part_contains_ingredients(workflow_with_recipe):
    # Ingredients must be formatted as "- name amount unit" for legibility
    msg = workflow_with_recipe._format_message()[1]
    assert "- Chicken 300.0 g" in msg
    assert "- Carrot 2.0 piece" in msg


def test_format_message_third_part_contains_numbered_instructions(workflow_with_recipe):
    # Steps must be 1-indexed; zero-indexed or flat lists break the cooking flow
    msg = workflow_with_recipe._format_message()[2]
    assert "1. Chop vegetables" in msg
    assert "2. Simmer chicken" in msg
    assert "3. Season to taste" in msg


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


async def test_run_success_returns_messages_and_recipe(mock_prompt_store):
    # End-to-end happy path: caller receives a list[str] and a Recipe, not None
    wf = ParseRecipeWorkflow(
        make_mock_model(make_parse_recipe_input()),
        "https://example.com/recipe",
        mock_prompt_store,
    )
    with patch(
        "agent.workflows.parse_recipe.web_fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = "page content"
        msgs, recipe = await wf.run()
    assert isinstance(msgs, list)
    assert len(msgs) == 3
    assert recipe is not None


async def test_run_calls_web_fetch_with_correct_url(mock_prompt_store):
    # Wrong URL means wrong page content is fetched — must verify the URL is forwarded unchanged
    url = "https://example.com/recipe"
    wf = ParseRecipeWorkflow(
        make_mock_model(make_parse_recipe_input()), url, mock_prompt_store
    )
    with patch(
        "agent.workflows.parse_recipe.web_fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = "page content"
        await wf.run()
    mock_fetch.assert_called_once_with(url)


async def test_run_calls_backup_web_fetch_when_primary_parse_fails(mock_prompt_store):
    # Primary fetch returns content the LLM can't turn into a valid recipe — backup must be attempted
    invalid_input = make_parse_recipe_input(ingredients=[])  # fails _validate_recipe
    wf = ParseRecipeWorkflow(
        make_mock_model(invalid_input), "https://example.com/recipe", mock_prompt_store
    )
    with (
        patch(
            "agent.workflows.parse_recipe.web_fetch", new_callable=AsyncMock
        ) as mock_primary,
        patch(
            "agent.workflows.parse_recipe.backup_web_fetch", new_callable=AsyncMock
        ) as mock_backup,
    ):
        mock_primary.return_value = "primary content"
        mock_backup.return_value = "backup content"
        await wf.run()
    mock_backup.assert_called_once_with("https://example.com/recipe")


async def test_run_returns_recipe_when_backup_web_fetch_succeeds(mock_prompt_store):
    # Primary parse fails validation; backup produces a valid recipe — caller gets list[str] + Recipe
    invalid_input = make_parse_recipe_input(ingredients=[])
    valid_input = make_parse_recipe_input()
    model = MagicMock(spec=BaseChatModel)
    model.with_structured_output.return_value.ainvoke = AsyncMock(
        side_effect=[invalid_input, valid_input]
    )
    wf = ParseRecipeWorkflow(model, "https://example.com/recipe", mock_prompt_store)
    with (
        patch(
            "agent.workflows.parse_recipe.web_fetch", new_callable=AsyncMock
        ) as mock_primary,
        patch(
            "agent.workflows.parse_recipe.backup_web_fetch", new_callable=AsyncMock
        ) as mock_backup,
    ):
        mock_primary.return_value = "primary content"
        mock_backup.return_value = "backup content"
        msgs, recipe = await wf.run()
    assert isinstance(msgs, list)
    assert recipe is not None


async def test_run_returns_error_when_both_fetches_fail(mock_prompt_store):
    # Both primary and backup return unparseable content — caller must get an error string, not None
    invalid_input = make_parse_recipe_input(ingredients=[])
    model = MagicMock(spec=BaseChatModel)
    model.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=invalid_input
    )
    wf = ParseRecipeWorkflow(model, "https://example.com/recipe", mock_prompt_store)
    with (
        patch(
            "agent.workflows.parse_recipe.web_fetch", new_callable=AsyncMock
        ) as mock_primary,
        patch(
            "agent.workflows.parse_recipe.backup_web_fetch", new_callable=AsyncMock
        ) as mock_backup,
    ):
        mock_primary.return_value = "primary content"
        mock_backup.return_value = "backup content"
        msgs, recipe = await wf.run()
    assert isinstance(msgs, str)
    assert recipe is None


async def test_run_validation_error_returns_error_string_and_none(mock_prompt_store):
    # LLM returns malformed output; caller must get a readable string, not a crash or ValidationError
    wf = ParseRecipeWorkflow(
        MagicMock(spec=BaseChatModel), "https://example.com/recipe", mock_prompt_store
    )
    with patch(
        "agent.workflows.parse_recipe.web_fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = "page content"
        wf.model.with_structured_output.return_value.ainvoke = AsyncMock(
            side_effect=make_validation_error()
        )
        msgs, recipe = await wf.run()
    assert isinstance(msgs, str)
    assert recipe is None


async def test_run_value_error_returns_error_string_and_none(mock_prompt_store):
    # LLM call itself raises; caller must get a readable string, not a raw exception
    wf = ParseRecipeWorkflow(
        MagicMock(spec=BaseChatModel), "https://example.com/recipe", mock_prompt_store
    )
    with patch(
        "agent.workflows.parse_recipe.web_fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = "page content"
        wf.model.with_structured_output.return_value.ainvoke = AsyncMock(
            side_effect=ValueError("bad output")
        )
        msgs, recipe = await wf.run()
    assert isinstance(msgs, str)
    assert recipe is None


async def test_run_connect_error_returns_error_string_and_none(mock_prompt_store):
    # URL is unreachable; caller must get a readable string and not httpx.ConnectError
    wf = ParseRecipeWorkflow(
        MagicMock(spec=BaseChatModel), "https://example.com/recipe", mock_prompt_store
    )
    with patch(
        "agent.workflows.parse_recipe.web_fetch",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("connection refused"),
    ):
        msgs, recipe = await wf.run()
    assert isinstance(msgs, str)
    assert recipe is None


async def test_run_unexpected_exception_returns_error_string_and_none(
    mock_prompt_store,
):
    # Unknown failure; the catch-all branch must still return a tuple, not re-raise
    wf = ParseRecipeWorkflow(
        MagicMock(spec=BaseChatModel), "https://example.com/recipe", mock_prompt_store
    )
    with patch(
        "agent.workflows.parse_recipe.web_fetch",
        new_callable=AsyncMock,
        side_effect=RuntimeError("something broke"),
    ):
        msgs, recipe = await wf.run()
    assert isinstance(msgs, str)
    assert recipe is None
