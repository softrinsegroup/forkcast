import pytest

from agent.workflows.chat import ChatWorkflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workflow():
    return ChatWorkflow()


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


async def test_run_returns_tuple(workflow):
    result = await workflow.run()
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert result[1] is None


async def test_run_returns_nonempty_string(workflow):
    result = await workflow.run()
    assert len(result[0]) > 0


async def test_run_mentions_plan_meals(workflow):
    result = await workflow.run()
    assert "plan" in result[0].lower()


async def test_run_mentions_add_recipe(workflow):
    result = await workflow.run()
    assert "add" in result[0].lower() or "recipe" in result[0].lower()


async def test_run_is_idempotent(workflow):
    first = await workflow.run()
    second = await workflow.run()
    assert first == second
