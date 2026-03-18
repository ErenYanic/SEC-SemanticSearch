"use client";

import { useStatus } from "@/hooks/useStatus";

/**
 * Persistent banner shown when the API is running in demo mode.
 *
 * Fetches the status via `useStatus()` (cache-shared with Dashboard
 * and other pages via React Query's `["status"]` key). Renders a
 * yellow/amber banner at the top of the page when `demo_mode` is true.
 *
 * Non-blocking: always renders children (the app layout) regardless
 * of the status fetch result. The banner is purely informational.
 */
export function DemoBanner({ children }: { children: React.ReactNode }) {
  const { data } = useStatus();

  return (
    <>
      {data?.demo_mode && (
        <div
          role="status"
          className="bg-amber-50 border-b border-amber-200 px-4 py-2 text-center text-sm text-amber-800 dark:bg-amber-900/30 dark:border-amber-700 dark:text-amber-200"
        >
          Demo — Data resets nightly at midnight UTC
        </div>
      )}
      {children}
    </>
  );
}
