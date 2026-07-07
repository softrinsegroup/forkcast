import { useEffect, useState } from "react";
import { CalendarDays, Loader2 } from "lucide-react";
import { getCurrentMealPlan, UnauthorizedError } from "@/lib/api";
import type { MealPlan } from "@/lib/types";
import { DayCard } from "./DayCard";
import { ShoppingList } from "./ShoppingList";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

type State =
  | { status: "loading" }
  | { status: "empty" }
  | { status: "ready"; plan: MealPlan }
  | { status: "error"; message: string };

export function MealPlanView() {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let active = true;
    getCurrentMealPlan()
      .then((plan) => {
        if (!active) return;
        setState(plan ? { status: "ready", plan } : { status: "empty" });
      })
      .catch((err) => {
        if (!active) return;
        const message = err instanceof UnauthorizedError ? "Please sign in again." : String(err);
        setState({ status: "error", message });
      });
    return () => {
      active = false;
    };
  }, []);

  if (state.status === "loading") {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="flex h-full items-center justify-center p-4 text-center text-sm text-muted-foreground">
        Couldn't load your meal plan. {state.message}
      </div>
    );
  }

  if (state.status === "empty") {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-4 text-center">
        <CalendarDays className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          No meal plan yet. Head to Chat and ask the agent to plan your week.
        </p>
      </div>
    );
  }

  const { plan } = state;
  // recipe[i] maps to day i (Mon–Sun); extras overflow past Sunday.
  const dayCount = Math.max(DAYS.length, plan.recipes.length);

  return (
    <div className="h-full space-y-4 overflow-y-auto p-4">
      <div className="text-sm text-muted-foreground">Week of {plan.timestamp}</div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: dayCount }).map((_, i) => (
          <DayCard key={i} day={DAYS[i] ?? `Extra ${i - DAYS.length + 1}`} recipe={plan.recipes[i]} />
        ))}
      </div>
      <ShoppingList items={plan.shopping_items} />
    </div>
  );
}
