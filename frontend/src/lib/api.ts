import type { MealPlan, Recipe, User } from "./types";

// All backend calls are same-origin (Vite proxy in dev, FastAPI static in prod),
// so we always send the session cookie.
const opts: RequestInit = { credentials: "include" };

export class UnauthorizedError extends Error {}

export async function getMe(): Promise<User> {
  const res = await fetch("/users/me", opts);
  if (res.status === 401) throw new UnauthorizedError();
  if (!res.ok) throw new Error(`GET /users/me failed: ${res.status}`);
  const body = await res.json();
  return body.user as User;
}

/** Returns null when the user has no plan for the current week. */
export async function getCurrentMealPlan(): Promise<MealPlan | null> {
  const res = await fetch("/meal-plans/current", opts);
  if (res.status === 404) return null;
  if (res.status === 401) throw new UnauthorizedError();
  if (!res.ok) throw new Error(`GET /meal-plans/current failed: ${res.status}`);
  const body = await res.json();
  return (body ?? null) as MealPlan | null;
}

export async function getRecipe(id: number): Promise<Recipe> {
  const res = await fetch(`/recipes/${id}`, opts);
  if (!res.ok) throw new Error(`GET /recipes/${id} failed: ${res.status}`);
  return (await res.json()) as Recipe;
}

/** Opens the chat SSE stream for a message. Caller consumes via parseSSEStream. */
export function openChatStream(message: string, signal: AbortSignal): Promise<Response> {
  return fetch(`/chat/stream?message=${encodeURIComponent(message)}`, {
    ...opts,
    signal,
    headers: { Accept: "text/event-stream" },
  });
}
