/**
 * Tests for admin login rate limiter (F5 — brute-force protection).
 */
import { describe, it, expect, beforeEach } from "vitest";

import {
  checkAdminLoginRate,
  recordFailedAdminLogin,
  resetAdminLoginRateLimit,
} from "@/lib/adminAuth";

describe("Admin login rate limiter", () => {
  beforeEach(() => {
    resetAdminLoginRateLimit();
  });

  it("allows the first attempt", () => {
    const result = checkAdminLoginRate("192.168.1.1");
    expect(result.allowed).toBe(true);
    expect(result.retryAfter).toBe(0);
  });

  it("allows up to 5 failed attempts within a minute", () => {
    const ip = "10.0.0.1";
    for (let i = 0; i < 5; i++) {
      recordFailedAdminLogin(ip);
    }
    // The 5 failures are recorded; the next CHECK should be blocked.
    const result = checkAdminLoginRate(ip);
    expect(result.allowed).toBe(false);
    expect(result.retryAfter).toBeGreaterThanOrEqual(1);
  });

  it("blocks the 6th attempt after 5 failures", () => {
    const ip = "172.16.0.1";
    for (let i = 0; i < 5; i++) {
      recordFailedAdminLogin(ip);
    }
    const result = checkAdminLoginRate(ip);
    expect(result.allowed).toBe(false);
  });

  it("isolates rate limits per IP", () => {
    const attacker = "evil.attacker";
    const legitimate = "good.user";

    // Exhaust attacker's budget
    for (let i = 0; i < 5; i++) {
      recordFailedAdminLogin(attacker);
    }

    // Attacker is blocked
    expect(checkAdminLoginRate(attacker).allowed).toBe(false);
    // Legitimate user is not affected
    expect(checkAdminLoginRate(legitimate).allowed).toBe(true);
  });

  it("returns retry-after in seconds", () => {
    const ip = "10.0.0.2";
    for (let i = 0; i < 5; i++) {
      recordFailedAdminLogin(ip);
    }
    const result = checkAdminLoginRate(ip);
    expect(result.allowed).toBe(false);
    expect(typeof result.retryAfter).toBe("number");
    expect(result.retryAfter).toBeGreaterThanOrEqual(1);
    expect(result.retryAfter).toBeLessThanOrEqual(62); // window is 60s + 1
  });

  it("reset clears all tracked attempts", () => {
    const ip = "10.0.0.3";
    for (let i = 0; i < 5; i++) {
      recordFailedAdminLogin(ip);
    }
    expect(checkAdminLoginRate(ip).allowed).toBe(false);

    resetAdminLoginRateLimit();
    expect(checkAdminLoginRate(ip).allowed).toBe(true);
  });
});
