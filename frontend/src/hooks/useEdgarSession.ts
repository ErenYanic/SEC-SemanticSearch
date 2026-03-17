/**
 * Hook for managing per-session EDGAR credentials.
 *
 * EDGAR credentials (name + email) are stored in `sessionStorage` so they:
 *   - Survive page refreshes within the same tab
 *   - Auto-clear when the tab is closed (browser-native behaviour)
 *   - Are never sent to the server except via explicit HTTP headers
 *
 * The hook uses `useSyncExternalStore` (React 19-compliant) to read
 * from `sessionStorage` without `useState` + `useEffect`.
 */

import { useCallback, useSyncExternalStore } from "react";

// ---------------------------------------------------------------------------
// Storage keys
// ---------------------------------------------------------------------------

const EDGAR_NAME_KEY = "edgar_name";
const EDGAR_EMAIL_KEY = "edgar_email";

// ---------------------------------------------------------------------------
// External store subscribers
// ---------------------------------------------------------------------------

// `useSyncExternalStore` requires a `subscribe` function that registers
// a callback.  Since `sessionStorage` has no native change event within
// the same tab, we dispatch a custom event when we write.

const STORAGE_EVENT = "edgar-session-change";

function subscribe(callback: () => void): () => void {
  window.addEventListener(STORAGE_EVENT, callback);
  return () => window.removeEventListener(STORAGE_EVENT, callback);
}

/** Fire a custom event so all `useSyncExternalStore` subscribers re-read. */
function notifyChange(): void {
  window.dispatchEvent(new Event(STORAGE_EVENT));
}

// ---------------------------------------------------------------------------
// Snapshot functions
// ---------------------------------------------------------------------------

function getNameSnapshot(): string | null {
  return sessionStorage.getItem(EDGAR_NAME_KEY);
}

function getEmailSnapshot(): string | null {
  return sessionStorage.getItem(EDGAR_EMAIL_KEY);
}

/** SSR fallback — sessionStorage is not available on the server. */
function getServerSnapshot(): null {
  return null;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface EdgarSession {
  /** User's name for EDGAR identity. */
  name: string | null;
  /** User's email for EDGAR identity. */
  email: string | null;
  /** True when both name and email are set. */
  isAuthenticated: boolean;
  /** Store credentials in sessionStorage. */
  login: (name: string, email: string) => void;
  /** Clear credentials from sessionStorage. */
  logout: () => void;
}

export function useEdgarSession(): EdgarSession {
  const name = useSyncExternalStore(subscribe, getNameSnapshot, getServerSnapshot);
  const email = useSyncExternalStore(subscribe, getEmailSnapshot, getServerSnapshot);

  const login = useCallback((newName: string, newEmail: string) => {
    sessionStorage.setItem(EDGAR_NAME_KEY, newName.trim());
    sessionStorage.setItem(EDGAR_EMAIL_KEY, newEmail.trim());
    notifyChange();
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem(EDGAR_NAME_KEY);
    sessionStorage.removeItem(EDGAR_EMAIL_KEY);
    notifyChange();
  }, []);

  return {
    name,
    email,
    isAuthenticated: Boolean(name && email),
    login,
    logout,
  };
}
