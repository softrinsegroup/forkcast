import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";
import type { ChatItem } from "@/hooks/useChatStream";
import { RecipeCard } from "./RecipeCard";

export function MessageBubble({ item }: { item: ChatItem }) {
  if (item.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-2 text-sm text-primary-foreground">
          {item.text}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {item.blocks.map((block, i) =>
        block.type === "recipe" ? (
          <RecipeCard key={i} recipe={block.recipe} />
        ) : (
          <div
            key={i}
            className={cn(
              "max-w-[85%] rounded-2xl rounded-bl-sm bg-muted px-4 py-2 text-sm",
              "prose-sm break-words [&_ol]:my-1 [&_ol]:list-decimal [&_ol]:pl-5",
              "[&_ul]:my-1 [&_ul]:list-disc [&_ul]:pl-5 [&_p]:my-1 [&_a]:text-primary [&_a]:underline",
            )}
          >
            <ReactMarkdown>{block.text}</ReactMarkdown>
          </div>
        ),
      )}
    </div>
  );
}
