// Mirrors models/domain.py

export interface User {
  id: string;
  name: string | null;
  email: string;
}

export interface Ingredient {
  name: string;
  unit: string;
  amount: number;
}

export interface Recipe {
  id: number | null;
  name: string;
  instructions: string[];
  ingredients: Ingredient[];
  servings: number;
  prep_minutes: number;
  cook_minutes: number;
  tags: string[];
}

export interface ShoppingItem {
  ingredient_name: string;
  unit: string;
  amount: number;
}

export interface MealPlan {
  id: number;
  timestamp: string; // YYYY-MM-DD, week start
  recipes: Recipe[];
  shopping_items: ShoppingItem[];
}

// Parsed SSE events from GET /chat/stream
export type ChatEvent =
  | { kind: "token"; content: string }
  | { kind: "recipe"; recipe: Recipe }
  | { kind: "interrupt"; value: string }
  | { kind: "done" }
  | { kind: "error"; message: string };
