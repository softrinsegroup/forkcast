from uuid import UUID
from pydantic import BaseModel
from datetime import datetime, date


class Ingredient(BaseModel):
    id: int | None = None
    name: str
    unit: str
    amount: float


class Recipe(BaseModel):
    id: int | None = None
    name: str
    instructions: list[str]
    ingredients: list[Ingredient]
    servings: int
    prep_minutes: int
    cook_minutes: int
    tags: list[str]
    created_at: datetime
    embedded: bool


class ShoppingItem(BaseModel):
    id: int | None = None
    weekly_plan_id: int | None = None
    ingredient_name: str
    unit: str
    amount: float


class WeeklyPlan(BaseModel):
    id: int | None = None
    user_id: UUID
    timestamp: date
    recipe_ids: list[int]
    shopping_items: list[ShoppingItem]
    created_at: datetime


class User(BaseModel):
    id: UUID
    name: str | None = None
    email: str
    google_sub: str
    created_at: datetime


class UserCreate(BaseModel):
    name: str | None
    email: str
    google_sub: str
