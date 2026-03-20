import { timingSafeEqual, createHash } from "node:crypto";

import type { NextRequest } from "next/server";

export const ADMIN_SESSION_COOKIE = "sec_search_admin";

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