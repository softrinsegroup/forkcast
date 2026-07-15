import type { MealPlan, Recipe, User } from "./types";

// Base URL for the backend API. In production the app (app.forkcast.app) calls
// the API cross-origin at api.forkcast.app via VITE_API_BASE. In dev it is unset,
// so calls stay relative and the Vite proxy forwards them to :8000.
export const API_BASE = import.meta.env.VITE_API_BASE ?? "";

// app.forkcast.app and api.forkcast.app are the same site, so the Lax session
// cookie rides along on these credentialed requests.
const opts: RequestInit = { credentials: "include" };

export class UnauthorizedError extends Error {}

export async function getMe(): Promise<User> {
  const res = await fetch(`${API_BASE}/users/me`, opts);
  if (res.status === 401) throw new UnauthorizedError();
  if (!res.ok) throw new Error(`GET /users/me failed: ${res.status}`);
  const body = await res.json();
  return body.user as User;
}

/** Returns null when the user has no plan for the current week. */
export async function getCurrentMealPlan(): Promise<MealPlan | null> {
  const res = await fetch(`${API_BASE}/meal-plans/current`, opts);
  if (res.status === 404) return null;
  if (res.status === 401) throw new UnauthorizedError();
  if (!res.ok) throw new Error(`GET /meal-plans/current failed: ${res.status}`);
  const body = await res.json();
  return (body ?? null) as MealPlan | null;
}

export async function getRecipe(id: number): Promise<Recipe> {
  const res = await fetch(`${API_BASE}/recipes/${id}`, opts);
  if (!res.ok) throw new Error(`GET /recipes/${id} failed: ${res.status}`);
  return (await res.json()) as Recipe;
}

/** Opens the chat SSE stream for a message. Caller consumes via parseSSEStream. */
export function openChatStream(message: string, signal: AbortSignal): Promise<Response> {
  return fetch(`${API_BASE}/chat/stream?message=${encodeURIComponent(message)}`, {
    ...opts,
    signal,
    headers: { Accept: "text/event-stream" },
  });
}
