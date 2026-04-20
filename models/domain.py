from pydantic import BaseModel
from datetime import datetime, date


class Ingredient(BaseModel):
    id: int
    name: str
    unit: str
    amount: float


class Recipe(BaseModel):
    id: int
    name: str
    instructions: list[str]
    ingredients: list[Ingredient]
    servings: int
    prep_minutes: int
    cook_minutes: int
    tags: list[str]
    created_at: datetime


class WeeklyPlan(BaseModel):
    timestamp: date
    recipe_ids: list[int]
    created_at: datetime


class ShoppingItem(BaseModel):
    ingredient_name: str
    unit: str
    amount: float
    recipe_ids: list[int]
