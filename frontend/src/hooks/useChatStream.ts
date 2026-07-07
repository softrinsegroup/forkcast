import { useCallback, useRef, useState } from "react";
import { openChatStream } from "@/lib/api";
import { parseSSEStream } from "@/lib/sse";
import type { Recipe } from "@/lib/types";

export type AssistantBlock =
  | { type: "text"; text: string }
  | { type: "recipe"; recipe: Recipe };

export type ChatItem =
  | { role: "user"; text: string }
  | { role: "assistant"; blocks: AssistantBlock[] };

export interface ChatStream {
  messages: ChatItem[];
  streaming: boolean;
  /** Set when the agent is waiting for a confirmation; the next send resumes it. */
  interrupt: string | null;
  error: string | null;
  send: (message: string) => Promise<void>;
}

/** Append a text chunk to the assistant's last text block, or start a new one. */
function appendToken(blocks: AssistantBlock[], content: string): AssistantBlock[] {
  const last = blocks[blocks.length - 1];
  if (last?.type === "text") {
    return [...blocks.slice(0, -1), { type: "text", text: last.text + content }];
  }
  return [...blocks, { type: "text", text: content }];
}

export function useChatStream(): ChatStream {
  const [messages, setMessages] = useState<ChatItem[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [interrupt, setInterrupt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Mutate the trailing assistant turn's blocks.
  const updateAssistant = useCallback(
    (fn: (blocks: AssistantBlock[]) => AssistantBlock[]) => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role !== "assistant") return prev;
        return [...prev.slice(0, -1), { role: "assistant", blocks: fn(last.blocks) }];
      });
    },
    [],
  );

  const send = useCallback(
    async (message: string) => {
      const text = message.trim();
      if (!text || streaming) return;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setInterrupt(null);
      setError(null);
      setStreaming(true);
      setMessages((prev) => [
        ...prev,
        { role: "user", text },
        { role: "assistant", blocks: [] },
      ]);

      try {
        const res = await openChatStream(text, controller.signal);
        if (!res.ok || !res.body) throw new Error(`Chat request failed: ${res.status}`);

        for await (const event of parseSSEStream(res.body)) {
          switch (event.kind) {
            case "token":
              updateAssistant((b) => appendToken(b, event.content));
              break;
            case "recipe":
              updateAssistant((b) => [...b, { type: "recipe", recipe: event.recipe }]);
              break;
            case "interrupt":
              setInterrupt(event.value);
              break;
            case "error":
              setError(event.message);
              break;
            case "done":
              break;
          }
        }
      } catch (err) {
        if (!controller.signal.aborted) setError(String(err));
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
          setStreaming(false);
        }
      }
    },
    [streaming, updateAssistant],
  );

  return { messages, streaming, interrupt, error, send };
}
