"use client";

/**
 * Client-side providers wrapper.
 *
 * Groups all providers that need "use client" into a single component
 * so the root `layout.tsx` can remain a Server Component.
 *
 * Providers (outermost → innermost):
 *   1. **QueryClientProvider** — React Query's cache and state manager.
 *      Every component that calls `useQuery()` or `useMutation()` needs
 *      this ancestor.  Think of it like a database connection pool that
 *      all your data-fetching code shares.
 *
 *   2. **ThemeProvider** — our dark/light mode context.
 *
 *   3. **ToastProvider** — global notification system.  Innermost so
 *      toasts inherit the current theme (they use Tailwind `dark:`
 *      classes which depend on ThemeProvider having applied the
 *      `dark` class to `<html>`).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { ThemeProvider } from "./layout/ThemeProvider";
import { ToastProvider } from "./ui/Toast";

export function Providers({ children }: { children: ReactNode }) {
  // Create the QueryClient inside `useState` so it's created once per
  // browser tab and survives across re-renders.  If we created it
  // outside the component, it would be shared across all server-side
  // requests (a security issue in SSR).
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Don't refetch when the browser tab regains focus.
            // This prevents surprising re-fetches for the user.
            refetchOnWindowFocus: false,

            // Keep data in cache for 30 seconds before considering
            // it stale.  Avoids redundant API calls when navigating
            // between pages quickly.
            staleTime: 30_000,

            // Retry failed requests once (default is 3, which is
            // too aggressive for a local single-user app).
            retry: 1,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          {children}
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}