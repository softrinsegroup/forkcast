CLASSIFY_INTENT_TOOL = {
    "name": "classify_intent",
    "description": "Classifies the intent of a message to determine what action it should take next.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": ["plan", "chat"]},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": ["intent", "confidence"],
    },
}


CREATE_MEAL_PLAN_TOOL = {
    "name": "create_meal_plan",
    "description": "Select exactly 5 recipes from the recipe bank for the upcoming week (Mon-Fri). Minimize overlap with the previous week recipe_ids.",
    "input_schema": {
        "type": "object",
        "properties": {
            "recipe_ids": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 0,
                "maxItems": 5,
            },
            "notes": {"type": "string"},  # rationale + any caveats
        },
        "required": ["recipe_ids", "notes"],
    },
}

PARSE_RECIPE_TOOL = {
    "name": "parse_recipe",
    "description": "Parse recipe extracted from a URL.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "ingredients": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "amount": {"type": "number"},
                        "unit": {"type": "string"},
                    },
                    "required": ["name", "amount", "unit"],
                },
            },
            "instructions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "servings": {"type": "integer"},
            "prep_minutes": {"type": "integer"},
            "cook_minutes": {"type": "integer"},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "name",
            "ingredients",
            "instructions",
            "servings",
            "prep_minutes",
            "cook_minutes",
            "tags",
        ],
    },
}
