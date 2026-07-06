import { describe, expect, it } from "vitest";
import { parseSSEBlock, parseSSEStream } from "./sse";
import type { ChatEvent } from "./types";

// Why: the frontend's whole chat behavior hinges on correctly discriminating the
// backend's SSE variants (api/chat.py). A parser that mislabels an event breaks
// streaming, recipe cards, or the interrupt/resume flow — so assert each kind.
describe("parseSSEBlock", () => {
  it("parses a token from a default (unnamed) event", () => {
    expect(parseSSEBlock('data: {"type":"token","content":"Hello"}')).toEqual({
      kind: "token",
      content: "Hello",
    });
  });

  it("parses a structured recipe event", () => {
    const recipe = { id: 1, name: "Soup", instructions: [], ingredients: [] };
    const block = `data: ${JSON.stringify({ type: "recipe", recipe })}`;
    expect(parseSSEBlock(block)).toEqual({ kind: "recipe", recipe });
  });

  it("parses a named interrupt event and keeps the prompt string", () => {
    expect(parseSSEBlock('event: interrupt\ndata: {"value":"Confirm?"}')).toEqual({
      kind: "interrupt",
      value: "Confirm?",
    });
  });

  it("parses done and error", () => {
    expect(parseSSEBlock("event: done\ndata: {}")).toEqual({ kind: "done" });
    expect(parseSSEBlock('event: error\ndata: {"message":"boom"}')).toEqual({
      kind: "error",
      message: "boom",
    });
  });

  it("ignores comments/heartbeats and malformed data", () => {
    expect(parseSSEBlock(": keep-alive")).toBeNull();
    expect(parseSSEBlock("data: not-json")).toBeNull();
  });
});

describe("parseSSEStream", () => {
  it("reassembles events split across chunk boundaries", async () => {
    const chunks = [
      'data: {"type":"token","content":"He',
      'llo"}\n\ndata: {"type":"token","content":" world"}\n\n',
      "event: done\ndata: {}\n\n",
    ];
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        const enc = new TextEncoder();
        for (const c of chunks) controller.enqueue(enc.encode(c));
        controller.close();
      },
    });

    const events: ChatEvent[] = [];
    for await (const e of parseSSEStream(body)) events.push(e);

    expect(events).toEqual([
      { kind: "token", content: "Hello" },
      { kind: "token", content: " world" },
      { kind: "done" },
    ]);
  });
});
