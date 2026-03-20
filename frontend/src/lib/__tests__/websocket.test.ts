import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { IngestWebSocket } from "../websocket";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readonly url: string;
  readyState = MockWebSocket.CONNECTING;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(message: string): void {
    this.sent.push(message);
  }

  close(): void {
    this.readyState = MockWebSocket.CLOSED;
  }

  open(): void {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }

  failWithClose(code: number): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({ code } as CloseEvent);
  }
}

describe("IngestWebSocket", () => {
  const originalWebSocket = globalThis.WebSocket;
  const originalLocation = window.location;

  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
    vi.stubGlobal("location", {
      ...originalLocation,
      protocol: "https:",
      host: "example.test",
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    globalThis.WebSocket = originalWebSocket;
  });

  it("opens without api_key in the URL and sends auth as the first message", () => {
    vi.stubEnv("NEXT_PUBLIC_API_KEY", "public-api-key");

    const socket = new IngestWebSocket("task-123", vi.fn());
    socket.connect();

    const ws = MockWebSocket.instances[0];
    expect(ws.url).toBe("wss://example.test/ws/ingest/task-123");

    ws.open();

    expect(ws.sent).toEqual([
      JSON.stringify({ type: "auth", api_key: "public-api-key" }),
    ]);
  });

  it("stops reconnecting after a fatal auth close code", () => {
    vi.stubEnv("NEXT_PUBLIC_API_KEY", "public-api-key");
    const onClose = vi.fn();

    const socket = new IngestWebSocket("task-123", vi.fn(), onClose);
    socket.connect();

    const ws = MockWebSocket.instances[0];
    ws.failWithClose(4001);

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(MockWebSocket.instances).toHaveLength(1);
  });
});