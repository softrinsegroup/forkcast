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
    id: int
    timestamp: date
    recipe_ids: list[int]
    created_at: datetime


class ShoppingItem(BaseModel):
    id: int
    weekly_plan_id: int
    ingredient_name: str
    unit: str
    amount: float
