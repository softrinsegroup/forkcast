import { Clock, Flame, Users } from "lucide-react";
import type { Recipe } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function RecipeCard({ recipe }: { recipe: Recipe }) {
  const totalMinutes = recipe.prep_minutes + recipe.cook_minutes;

  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle>{recipe.name}</CardTitle>
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Clock className="size-3.5" /> {totalMinutes} min
          </span>
          <span className="inline-flex items-center gap-1">
            <Flame className="size-3.5" /> {recipe.prep_minutes} prep / {recipe.cook_minutes} cook
          </span>
          <span className="inline-flex items-center gap-1">
            <Users className="size-3.5" /> {recipe.servings} servings
          </span>
        </div>
        {recipe.tags.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1.5">
            {recipe.tags.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </CardHeader>

      <CardContent className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <section>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Ingredients
          </h4>
          <ul className="space-y-1">
            {recipe.ingredients.map((ing, i) => (
              <li key={i} className="flex justify-between gap-2">
                <span>{ing.name}</span>
                <span className="shrink-0 text-muted-foreground">
                  {ing.amount} {ing.unit}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Instructions
          </h4>
          <ol className="space-y-2">
            {recipe.instructions.map((step, i) => (
              <li key={i} className="flex gap-2">
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
                  {i + 1}
                </span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </section>
      </CardContent>
    </Card>
  );
}
