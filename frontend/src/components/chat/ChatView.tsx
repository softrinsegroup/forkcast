import { useEffect, useRef, useState } from "react";
import { Loader2, Send } from "lucide-react";
import { useChatStream } from "@/hooks/useChatStream";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MessageBubble } from "./MessageBubble";
import { InterruptPrompt } from "./InterruptPrompt";

export function ChatView() {
  const { messages, streaming, interrupt, error, send } = useChatStream();
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Autoscroll to newest content.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, interrupt]);

  const submit = () => {
    const text = draft;
    setDraft("");
    void send(text);
  };

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="mt-16 text-center text-sm text-muted-foreground">
            Ask me to plan your week, save a recipe from a URL, or build a shopping list.
          </div>
        )}
        {messages.map((item, i) => (
          <MessageBubble key={i} item={item} />
        ))}

        {interrupt && (
          <InterruptPrompt value={interrupt} disabled={streaming} onAnswer={(a) => void send(a)} />
        )}
        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}
      </div>

      <div className="border-t p-3">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Message the meal prep agent…"
            disabled={streaming}
            autoFocus
          />
          <Button type="submit" size="icon" disabled={streaming || !draft.trim()}>
            {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </form>
      </div>
    </div>
  );
}
