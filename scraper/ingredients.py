import re

from models import Ingredient

# Canonical units keyed by every spelling we accept. Values match the units
# the backend's LLM parse path produces.
_UNIT_ALIASES = {
    "cup": "cup",
    "cups": "cup",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tbsp": "tbsp",
    "tbs": "tbsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tsp": "tsp",
    "ounce": "oz",
    "ounces": "oz",
    "oz": "oz",
    "pound": "lb",
    "pounds": "lb",
    "lb": "lb",
    "lbs": "lb",
    "gram": "g",
    "grams": "g",
    "g": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "kg": "kg",
    "milliliter": "ml",
    "milliliters": "ml",
    "ml": "ml",
    "liter": "l",
    "liters": "l",
    "l": "l",
    "clove": "clove",
    "cloves": "clove",
    "can": "can",
    "cans": "can",
    "pinch": "pinch",
    "pinches": "pinch",
    "slice": "slice",
    "slices": "slice",
    "piece": "piece",
    "pieces": "piece",
    "stick": "stick",
    "sticks": "stick",
    "bunch": "bunch",
    "bunches": "bunch",
    "head": "head",
    "heads": "head",
    "package": "package",
    "packages": "package",
    "pkg": "package",
}

_UNICODE_FRACTIONS = {
    "¼": 0.25,
    "½": 0.5,
    "¾": 0.75,
    "⅓": 1 / 3,
    "⅔": 2 / 3,
    "⅛": 0.125,
    "⅜": 0.375,
    "⅝": 0.625,
    "⅞": 0.875,
}

_FRACTION_CHARS = "".join(_UNICODE_FRACTIONS)

# A quantity: "2", "1.5", "1/2", "1 1/2", "½", "1½". The (?![%\d]) guard keeps
# things like "2% milk" from being read as amount=2.
_NUM = rf"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?[{_FRACTION_CHARS}]?(?![%\d])|[{_FRACTION_CHARS}])"
# Optional range ("1-2", "1 to 2") — we keep the low end.
_QTY_RE = re.compile(rf"^\s*({_NUM})(?:\s*(?:-|–|to)\s*{_NUM})?\s+(.+)$")


def _to_number(token: str) -> float:
    token = token.strip()
    total = 0.0
    if token and token[-1] in _UNICODE_FRACTIONS:
        total += _UNICODE_FRACTIONS[token[-1]]
        token = token[:-1].strip()
    for part in token.split():
        if "/" in part:
            numerator, denominator = part.split("/", 1)
            total += float(numerator) / float(denominator)
        elif part:
            total += float(part)
    return total


def parse_ingredient(text: str, id: int = 0) -> Ingredient:
    """
    Best-effort deterministic parse of a recipeIngredient string.

    "2 cups flour" -> amount=2, unit="cup", name="flour". Anything we can't
    parse keeps the full raw string as the name with amount=0 — never lose
    data, a human-readable name is still useful in shopping lists.
    """
    raw = text.strip()
    match = _QTY_RE.match(raw)
    if not match:
        return Ingredient(id=id, name=raw, unit="", amount=0.0)

    amount = _to_number(match.group(1))
    rest = match.group(2).strip()

    unit = ""
    name = rest
    first, _, remainder = rest.partition(" ")
    canonical = _UNIT_ALIASES.get(first.lower().strip(".,"))
    if canonical and remainder.strip():
        unit = canonical
        name = remainder.strip()
        if name.lower().startswith("of "):
            name = name[3:]

    return Ingredient(id=id, name=name, unit=unit, amount=amount)
