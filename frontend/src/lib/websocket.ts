/**
 * WebSocket client for real-time ingestion progress.
 *
 * Wraps the browser's native `WebSocket` API with:
 *   - Automatic reconnection with exponential backoff
 *   - Typed message dispatching via a callback
 *   - Clean lifecycle management for React components
 *
 * Usage:
 *   const ws = new IngestWebSocket(taskId, (message) => {
 *     // message is fully typed as WsMessage
 *     if (message.type === "step") { ... }
 *   });
 *   ws.connect();
 *   // Later:
 *   ws.close();
 */

import type { WsMessage } from "./types";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Initial reconnection delay in milliseconds. */
const INITIAL_RETRY_MS = 1000;

/** Maximum reconnection delay (caps exponential growth). */
const MAX_RETRY_MS = 30_000;

/** Multiplier for exponential backoff (delay doubles each attempt). */
const BACKOFF_FACTOR = 2;

/** Message types that indicate the task has finished. */
const TERMINAL_TYPES = new Set(["completed", "failed", "cancelled"]);

// ---------------------------------------------------------------------------
// WebSocket client
// ---------------------------------------------------------------------------

export class IngestWebSocket {
  private ws: WebSocket | null = null;
  private retryCount = 0;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private closed = false;

  /**
   * @param taskId     The UUID of the ingestion task to monitor.
   * @param onMessage  Callback invoked for every parsed message from
   *                   the server.  The message is already typed as
   *                   `WsMessage`, so the caller can switch on `.type`.
   * @param onClose    Optional callback when the connection closes
   *                   permanently (either by the caller or after a
   *                   terminal message).
   */
  constructor(
    private readonly taskId: string,
    private readonly onMessage: (message: WsMessage) => void,
    private readonly onClose?: () => void,
  ) {}

  // -----------------------------------------------------------------------
  // Public API
  // -----------------------------------------------------------------------

  /** Open the WebSocket connection. Safe to call multiple times. */
  connect(): void {
    if (this.closed) return;
    this.cleanup();

    // Build the WebSocket URL.  In development, the Next.js proxy
    // rewrites /ws/* to the FastAPI backend.  We derive the URL from
    // the current page location so it works in both dev and production.
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const apiKey = process.env.NEXT_PUBLIC_API_KEY;
    const query = apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : "";
    const url = `${protocol}//${window.location.host}/ws/ingest/${this.taskId}${query}`;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      // Reset retry counter on successful connection.
      this.retryCount = 0;
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data) as WsMessage;
        this.onMessage(message);

        // If the task has reached a terminal state, stop reconnecting.
        if (TERMINAL_TYPES.has(message.type)) {
          this.closed = true;
          this.cleanup();
          this.onClose?.();
        }
      } catch {
        // Malformed JSON — log and ignore.
        console.warn("Failed to parse WebSocket message:", event.data);
      }
    };

    this.ws.onclose = () => {
      if (!this.closed) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      // The `onclose` handler will fire after `onerror`, which
      // triggers reconnection.  No additional handling needed here.
    };
  }

  /** Permanently close the connection (no reconnection). */
  close(): void {
    this.closed = true;
    this.cleanup();
    this.onClose?.();
  }

  /** Whether the underlying WebSocket is currently open. */
  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // -----------------------------------------------------------------------
  // Internal
  // -----------------------------------------------------------------------

  /**
   * Schedule a reconnection attempt with exponential backoff.
   *
   * Delay sequence: 1s → 2s → 4s → 8s → 16s → 30s → 30s → ...
   */
  private scheduleReconnect(): void {
    if (this.closed) return;

    const delay = Math.min(
      INITIAL_RETRY_MS * BACKOFF_FACTOR ** this.retryCount,
      MAX_RETRY_MS,
    );
    this.retryCount++;

    this.retryTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  /** Clean up the current connection and any pending retry timer. */
  private cleanup(): void {
    if (this.retryTimer !== null) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }

    if (this.ws) {
      // Remove handlers to avoid stale callbacks.
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;

      if (
        this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING
      ) {
        this.ws.close();
      }
      this.ws = null;
    }
  }
}