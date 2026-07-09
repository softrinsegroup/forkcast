import { useState } from "react";
import { Check, Copy, ShoppingCart } from "lucide-react";
import type { ShoppingItem } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function formatChecklist(items: ShoppingItem[]): string {
  return items
    .map((item) =>
      `- [ ] ${[item.amount, item.unit, item.ingredient_name]
        .filter((part) => part !== "" && part != null)
        .join(" ")}`
    )
    .join("\n");
}

export function ShoppingList({ items }: { items: ShoppingItem[] }) {
  const [status, setStatus] = useState<"idle" | "copied" | "error">("idle");

  async function handleCopy() {
    const text = formatChecklist(items);
    try {
      await navigator.clipboard.writeText(text);
      setStatus("copied");
      setTimeout(() => setStatus("idle"), 2000);
    } catch {
      setStatus("error");
      setTimeout(() => setStatus("idle"), 2000);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShoppingCart className="size-4 text-primary" /> Shopping List
        </CardTitle>
        <CardAction>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopy}
            disabled={items.length === 0}
          >
            {status === "copied" ? (
              <>
                <Check /> Copied
              </>
            ) : (
              <>
                <Copy /> {status === "error" ? "Copy failed" : "Copy"}
              </>
            )}
          </Button>
        </CardAction>
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
