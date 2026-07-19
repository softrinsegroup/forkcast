import json
import re
from typing import Any, Iterator

from bs4 import BeautifulSoup

from ingredients import parse_ingredient
from models import Recipe

# ISO-8601 duration, e.g. "PT1H30M", "PT45M", "P1DT2H".
_DURATION_RE = re.compile(
    r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:\d+(?:\.\d+)?S)?)?$"
)
_INT_RE = re.compile(r"\d+")


def _iter_nodes(data: Any) -> Iterator[dict]:
    """Yield every JSON-LD node, flattening lists and @graph containers."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_nodes(item)
    elif isinstance(data, dict):
        yield data
        yield from _iter_nodes(data.get("@graph", []))


def _is_recipe(node: dict) -> bool:
    node_type = node.get("@type", "")
    if isinstance(node_type, list):
        return "Recipe" in node_type
    return node_type == "Recipe"


def _clean(value: str) -> str:
    """Strip embedded HTML tags and entities from a JSON-LD string value."""
    return " ".join(BeautifulSoup(value, "html.parser").get_text().split())


def _duration_minutes(value: Any) -> int:
    if not isinstance(value, str):
        return 0
    match = _DURATION_RE.match(value.strip())
    if not match:
        return 0
    days, hours, minutes = (int(g) if g else 0 for g in match.groups())
    return days * 24 * 60 + hours * 60 + minutes


def _instructions(value: Any) -> list[str]:
    """Flatten recipeInstructions: plain strings, HowToStep, HowToSection."""
    if isinstance(value, str):
        return [_clean(value)] if value.strip() else []

    steps: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                if item.strip():
                    steps.append(_clean(item))
            elif isinstance(item, dict):
                if item.get("@type") == "HowToSection":
                    steps.extend(_instructions(item.get("itemListElement", [])))
                else:  # HowToStep (or untyped dict with text)
                    text = item.get("text") or item.get("name") or ""
                    if text.strip():
                        steps.append(_clean(text))
    return steps


def _servings(node: dict) -> int:
    value = node.get("recipeYield", "")
    if isinstance(value, list):
        value = value[0] if value else ""
    if isinstance(value, int):
        return value
    match = _INT_RE.search(str(value))
    return int(match.group()) if match else 0


def _tags(node: dict) -> list[str]:
    raw: list[str] = []
    keywords = node.get("keywords", "")
    if isinstance(keywords, str):
        raw.extend(keywords.split(","))
    elif isinstance(keywords, list):
        raw.extend(str(k) for k in keywords)
    for key in ("recipeCategory", "recipeCuisine"):
        value = node.get(key, [])
        raw.extend([value] if isinstance(value, str) else [str(v) for v in value])

    tags: list[str] = []
    for tag in raw:
        tag = tag.strip().lower()
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def extract_recipe(html: str, source_url: str) -> Recipe | None:
    """
    Deterministically extract a schema.org/Recipe from a page's JSON-LD.

    Returns None when the page has no usable Recipe node — which doubles as
    the "is this a recipe page at all?" filter during crawling.
    """
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        for node in _iter_nodes(data):
            if not _is_recipe(node):
                continue
            recipe = _node_to_recipe(node, source_url)
            if recipe is not None:
                return recipe
    return None


def _node_to_recipe(node: dict, source_url: str) -> Recipe | None:
    name = _clean(str(node.get("name", "")))
    instructions = _instructions(node.get("recipeInstructions", []))
    raw_ingredients = node.get("recipeIngredient", [])
    # Ingredient.id is required by the wire contract but ignored by the
    # backend on ingest (the DB assigns real ids).
    ingredients = [
        parse_ingredient(str(text), id=i)
        for i, text in enumerate(raw_ingredients)
        if str(text).strip()
    ]

    # Quality gate: looser than the backend's LLM parse validation on
    # purpose — JSON-LD legitimately omits times/servings/tags, and 0 is an
    # acceptable default for bulk ingest.
    if not name or not ingredients or not instructions:
        return None

    return Recipe(
        name=name,
        instructions=instructions,
        ingredients=ingredients,
        servings=_servings(node),
        prep_minutes=_duration_minutes(node.get("prepTime")),
        cook_minutes=_duration_minutes(node.get("cookTime")),
        tags=_tags(node),
        source_url=source_url,
    )
