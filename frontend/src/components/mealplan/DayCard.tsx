import { Clock, Users } from "lucide-react";
import type { Recipe } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";

export function DayCard({ day, recipe }: { day: string; recipe: Recipe | undefined }) {
  return (
    <Card size="sm">
      <CardContent className="flex flex-col gap-2">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {day}
        </div>
        {recipe ? (
          <>
            <div className="font-medium leading-tight">{recipe.name}</div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <Clock className="size-3.5" /> {recipe.prep_minutes + recipe.cook_minutes} min
              </span>
              <span className="inline-flex items-center gap-1">
                <Users className="size-3.5" /> {recipe.servings}
              </span>
            </div>
            {recipe.tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {recipe.tags.slice(0, 3).map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="text-muted-foreground">No meal</div>
        )}
      </CardContent>
    </Card>
  );
}
