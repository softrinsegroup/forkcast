import type { ChatEvent } from "./types";

/**
 * Parse a single SSE block (the text between blank-line separators) into a
 * typed ChatEvent. Returns null for blocks we don't recognize.
 *
 * The backend (api/chat.py) emits:
 *   - default event, data {type:"token"|"recipe", ...}
 *   - event: interrupt / done / error, with a JSON data payload
 */
export function parseSSEBlock(block: string): ChatEvent | null {
  let eventName = "message";
  const dataLines: string[] = [];

  for (const rawLine of block.split("\n")) {
    const line = rawLine.replace(/\r$/, "");
    if (line.startsWith(":")) continue; // comment / heartbeat
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).replace(/^ /, ""));
    }
  }

  if (dataLines.length === 0) return null;
  const data = dataLines.join("\n");

  let payload: any = {};
  try {
    payload = data ? JSON.parse(data) : {};
  } catch {
    return null;
  }

  switch (eventName) {
    case "interrupt":
      return { kind: "interrupt", value: String(payload.value ?? "") };
    case "done":
      return { kind: "done" };
    case "error":
      return { kind: "error", message: String(payload.message ?? "Unknown error") };
    case "message":
      if (payload.type === "token") return { kind: "token", content: payload.content ?? "" };
      if (payload.type === "recipe" && payload.recipe) return { kind: "recipe", recipe: payload.recipe };
      return null;
    default:
      return null;
  }
}

/**
 * Consume a fetch ReadableStream of SSE bytes and yield typed ChatEvents as
 * they arrive. Blocks are separated by a blank line ("\n\n").
 */
export async function* parseSSEStream(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<ChatEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const event = parseSSEBlock(block);
      if (event) yield event;
    }
  }

  // Flush any trailing block without a terminating blank line.
  const tail = parseSSEBlock(buffer);
  if (tail) yield tail;
}
