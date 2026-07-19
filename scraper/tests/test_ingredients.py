from ingredients import parse_ingredient

# Parsed amounts/units feed shopping-list aggregation, so the common formats
# must land in the same canonical units the LLM parse path produces.


def test_simple_amount_and_unit():
    ing = parse_ingredient("2 cups flour")
    assert ing.amount == 2.0
    assert ing.unit == "cup"
    assert ing.name == "flour"


def test_mixed_fraction():
    ing = parse_ingredient("1 1/2 tbsp olive oil")
    assert ing.amount == 1.5
    assert ing.unit == "tbsp"
    assert ing.name == "olive oil"


def test_unicode_fraction():
    ing = parse_ingredient("½ tsp salt")
    assert ing.amount == 0.5
    assert ing.unit == "tsp"
    assert ing.name == "salt"


def test_attached_unicode_fraction():
    ing = parse_ingredient("1½ cups milk")
    assert ing.amount == 1.5
    assert ing.unit == "cup"
    assert ing.name == "milk"


def test_range_takes_low_end():
    ing = parse_ingredient("1-2 cloves garlic")
    assert ing.amount == 1.0
    assert ing.unit == "clove"
    assert ing.name == "garlic"


def test_unit_alias_normalization():
    assert parse_ingredient("3 tablespoons butter").unit == "tbsp"
    assert parse_ingredient("2 pounds beef").unit == "lb"


def test_of_is_stripped_from_name():
    ing = parse_ingredient("1 pinch of saffron")
    assert ing.unit == "pinch"
    assert ing.name == "saffron"


def test_no_amount_keeps_raw_text():
    # Never lose data: unparseable lines keep the full string as the name so
    # a human can still read it in a shopping list.
    ing = parse_ingredient("salt to taste")
    assert ing.amount == 0.0
    assert ing.unit == ""
    assert ing.name == "salt to taste"


def test_amount_without_unit():
    ing = parse_ingredient("2 eggs")
    assert ing.amount == 2.0
    assert ing.unit == ""
    assert ing.name == "eggs"


def test_percentage_is_not_an_amount():
    # "2%" is part of the product name, not a quantity of 2.
    ing = parse_ingredient("2% milk")
    assert ing.amount == 0.0
    assert ing.name == "2% milk"
