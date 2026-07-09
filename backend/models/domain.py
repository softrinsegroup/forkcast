from uuid import UUID
from pydantic import BaseModel
from datetime import datetime, date


class Ingredient(BaseModel):
    id: int
    name: str
    unit: str
    amount: float


class IngredientCreate(BaseModel):
    recipe_id: int
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
    embedded: bool


class RecipeCreate(BaseModel):
    name: str
    instructions: list[str]
    ingredients: list[Ingredient]
    servings: int
    prep_minutes: int
    cook_minutes: int
    tags: list[str]


class ShoppingItem(BaseModel):
    id: int
    weekly_plan_id: int
    ingredient_name: str
    unit: str
    amount: float


class ShoppingItemCreate(BaseModel):
    ingredient_name: str
    unit: str
    amount: float


class WeeklyPlan(BaseModel):
    id: int
    user_id: UUID
    timestamp: date
    recipe_ids: list[int]
    shopping_items: list[ShoppingItem]
    created_at: datetime


class WeeklyPlanCreate(BaseModel):
    user_id: UUID
    timestamp: date
    recipe_ids: list[int]
    shopping_items: list[ShoppingItemCreate]


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
