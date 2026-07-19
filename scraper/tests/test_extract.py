from pathlib import Path

from extract import _duration_minutes, extract_recipe

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://example.com/recipes/test"


def load(name: str) -> str:
    return (FIXTURES / name).read_text()


# ---------------------------------------------------------------------------
# extract_recipe
# ---------------------------------------------------------------------------


def test_extract_plain_jsonld_recipe():
    # The common case: a single top-level Recipe node with string instructions.
    recipe = extract_recipe(load("recipe_jsonld.html"), URL)
    assert recipe is not None
    assert recipe.name == "Classic Pancakes"
    assert recipe.source_url == URL
    assert len(recipe.ingredients) == 4
    assert recipe.instructions == [
        "Whisk the dry ingredients together.",
        "Add eggs and milk, then stir until smooth.",
        "Cook on a hot griddle until golden.",
    ]
    assert recipe.servings == 4
    assert recipe.prep_minutes == 10
    assert recipe.cook_minutes == 15
    assert recipe.tags == ["breakfast", "easy", "american"]


def test_extract_graph_recipe_flattens_sections_and_strips_html():
    # WordPress SEO plugins wrap everything in @graph with list-valued @type,
    # HowToSection nesting, and HTML entities — all must flatten to clean steps.
    recipe = extract_recipe(load("recipe_graph.html"), URL)
    assert recipe is not None
    assert recipe.name == "Slow Roast Chicken"
    assert recipe.instructions == [
        "Pat the chicken dry.",
        "Rub with olive oil & salt.",
        "Roast at 300F for 3 hours.",
    ]
    assert recipe.servings == 6  # list-valued recipeYield
    assert recipe.cook_minutes == 180  # PT3H
    assert recipe.tags == ["dinner", "chicken", "main course"]


def test_extract_ingredient_parsing_end_to_end():
    recipe = extract_recipe(load("recipe_jsonld.html"), URL)
    flour = recipe.ingredients[0]
    assert flour.amount == 2.0
    assert flour.unit == "cup"
    assert flour.name == "all-purpose flour"
    # Unparseable-amount ingredient keeps raw text, loses nothing
    eggs = recipe.ingredients[3]
    assert eggs.amount == 2.0
    assert eggs.name == "eggs"


def test_extract_non_recipe_page_returns_none():
    # No Recipe node (and one malformed JSON-LD block) — the page must be
    # treated as "not a recipe", not crash the crawl.
    assert extract_recipe(load("non_recipe.html"), URL) is None


def test_extract_recipe_without_ingredients_returns_none():
    # Quality gate: a Recipe node missing its ingredients is unusable for
    # meal planning and must not be ingested.
    html = """<script type="application/ld+json">
    {"@type": "Recipe", "name": "Empty", "recipeInstructions": ["Do it"]}
    </script>"""
    assert extract_recipe(html, URL) is None


# ---------------------------------------------------------------------------
# _duration_minutes
# ---------------------------------------------------------------------------


def test_duration_parsing():
    assert _duration_minutes("PT1H30M") == 90
    assert _duration_minutes("PT45M") == 45
    assert _duration_minutes("PT2H") == 120
    assert _duration_minutes("P1DT2H") == 1560
    assert _duration_minutes(None) == 0
    assert _duration_minutes("garbage") == 0
