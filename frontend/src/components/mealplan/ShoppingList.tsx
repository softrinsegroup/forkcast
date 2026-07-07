import { ShoppingCart } from "lucide-react";
import type { ShoppingItem } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ShoppingList({ items }: { items: ShoppingItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShoppingCart className="size-4 text-primary" /> Shopping List
        </CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-muted-foreground">No items.</p>
        ) : (
          <ul className="grid gap-1.5 sm:grid-cols-2">
            {items.map((item, i) => (
              <li key={i} className="flex justify-between gap-2 border-b border-dashed py-1">
                <span>{item.ingredient_name}</span>
                <span className="shrink-0 text-muted-foreground">
                  {item.amount} {item.unit}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
