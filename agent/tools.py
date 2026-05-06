def create_meal_plan() -> list[int]:
    return {
        "name": "create_meal_plan",
        "description": "Select exactly 5 recipes from the recipe bank for the upcoming week (Mon-Fri). Minimize overlap with last week. Always call this tool.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipe_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 5,
                    "maxItems": 5,
                },
                "notes": {"type": "string"},  # rationale + any caveats
            },
            "required": ["recipe_ids", "notes"],
        },
    }
