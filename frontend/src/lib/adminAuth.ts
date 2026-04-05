import { timingSafeEqual, createHash } from "node:crypto";

import type { NextRequest } from "next/server";

export const ADMIN_SESSION_COOKIE = "sec_search_admin";

// ---------------------------------------------------------------------------
// Admin login rate limiter — brute-force protection (F5)
// ---------------------------------------------------------------------------

/** Maximum failed login attempts per IP within the sliding window. */
const _AUTH_MAX_ATTEMPTS = 5;
/** Sliding window duration in milliseconds (1 minute). */
const _AUTH_WINDOW_MS = 60_000;
/** Stale entry cleanup interval in milliseconds (5 minutes). */
const _AUTH_CLEANUP_INTERVAL_MS = 300_000;

/** Per-IP sliding window of failed login timestamps. */
const _failedAttempts = new Map<string, number[]>();
let _lastCleanup = Date.now();

function _pruneStaleEntries(): void {
  const now = Date.now();
  if (now - _lastCleanup < _AUTH_CLEANUP_INTERVAL_MS) return;
  _lastCleanup = now;
  const cutoff = now - _AUTH_WINDOW_MS;
  for (const [ip, timestamps] of _failedAttempts) {
    const fresh = timestamps.filter((t) => t > cutoff);
    if (fresh.length === 0) {
      _failedAttempts.delete(ip);
    } else {
      _failedAttempts.set(ip, fresh);
    }
  }
}

/**
 * Check whether *ip* is allowed to attempt an admin login.
 *
 * Returns ``{ allowed: true }`` or ``{ allowed: false, retryAfter }``
 * where *retryAfter* is the number of seconds to wait.
 */
export function checkAdminLoginRate(ip: string): {
  allowed: boolean;
  retryAfter: number;
} {
  _pruneStaleEntries();
  const now = Date.now();
  const cutoff = now - _AUTH_WINDOW_MS;
  const timestamps = (_failedAttempts.get(ip) ?? []).filter((t) => t > cutoff);
  _failedAttempts.set(ip, timestamps);

  if (timestamps.length >= _AUTH_MAX_ATTEMPTS) {
    const oldest = timestamps[0];
    const retryAfter = Math.ceil((_AUTH_WINDOW_MS - (now - oldest)) / 1000) + 1;
    return { allowed: false, retryAfter: Math.max(retryAfter, 1) };
  }
  return { allowed: true, retryAfter: 0 };
}

/** Record a failed admin login attempt from *ip*. */
export function recordFailedAdminLogin(ip: string): void {
  const timestamps = _failedAttempts.get(ip) ?? [];
  timestamps.push(Date.now());
  _failedAttempts.set(ip, timestamps);
}

/** Reset all tracked attempts (for testing). */
export function resetAdminLoginRateLimit(): void {
  _failedAttempts.clear();
}

const ADMIN_SESSION_SALT = "sec-search-admin-session-v1";

export function getConfiguredAdminKey(): string | null {
  const adminKey = process.env.ADMIN_API_KEY?.trim();
  return adminKey ? adminKey : null;
}

export function isAdminConfigured(): boolean {
  return getConfiguredAdminKey() !== null;
}

export function buildAdminSessionValue(adminKey: string): string {
  return createHash("sha256")
    .update(`${ADMIN_SESSION_SALT}:${adminKey}`)
    .digest("hex");
}

export function hasValidAdminSession(request: NextRequest): boolean {
  const adminKey = getConfiguredAdminKey();
  if (adminKey === null) {
    return true;
  }

  const cookieValue = request.cookies.get(ADMIN_SESSION_COOKIE)?.value;
  if (!cookieValue) {
    return false;
  }

  const expected = buildAdminSessionValue(adminKey);
  const actualBytes = Buffer.from(cookieValue, "utf-8");
  const expectedBytes = Buffer.from(expected, "utf-8");

  if (actualBytes.length !== expectedBytes.length) {
    return false;
  }

  return timingSafeEqual(actualBytes, expectedBytes);
}

export function getBackendBaseUrl(): string {
  return (process.env.INTERNAL_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
}

export function buildBackendAuthHeaders(): Headers {
  const headers = new Headers({ "Content-Type": "application/json" });
  const apiKey = process.env.NEXT_PUBLIC_API_KEY?.trim();
  const adminKey = getConfiguredAdminKey();

  if (apiKey) {
    headers.set("X-API-Key", apiKey);
  }
  if (adminKey) {
    headers.set("X-Admin-Key", adminKey);
  }

  return headers;
}