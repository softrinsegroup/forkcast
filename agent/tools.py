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
    "description": "Select exactly 5 recipes from the recipe bank for the upcoming week (Mon-Fri). Minimize overlap with last week. Always call this tool.",
    "input_schema": {
        "type": "object",
        "properties": {
            "recipe_ids": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 5,
                "maxItems": 5,
            },
            "notes": {"type": "string"},  # rationale + any caveats
        },
        "required": ["recipe_ids", "notes"],
    },
}
