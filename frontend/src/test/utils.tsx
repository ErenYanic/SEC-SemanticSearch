/**
 * Test utilities — `renderWithProviders()` wraps components in the
 * same provider tree used in production (`Providers.tsx`).
 *
 * Components that use `useToast()`, React Query hooks, or read the
 * theme context will throw without these providers. This wrapper
 * lets tests render components in a realistic environment without
 * manually constructing the provider tree in every test file.
 *
 * ## Differences from production `Providers.tsx`
 *
 * - **No ThemeProvider** — tests don't need dark mode toggling, and
 *   ThemeProvider reads `localStorage` which can add noise. Components
 *   using `dark:` Tailwind classes render the light variant by default.
 * - **Fresh QueryClient per test** — prevents cache leaks between tests.
 *   `retry: false` ensures failed queries don't hang the test runner.
 */

import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "@/components/ui/Toast";
import { type ReactElement, type ReactNode } from "react";

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function AllProviders({ children }: { children: ReactNode }) {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}

/**
 * Renders a component wrapped in all necessary providers.
 *
 * Usage:
 * ```ts
 * const { getByText } = renderWithProviders(<Button>Click me</Button>);
 * expect(getByText("Click me")).toBeInTheDocument();
 * ```
 */
export function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">,
) {
  return render(ui, { wrapper: AllProviders, ...options });
}

/** Re-export everything from @testing-library/react for convenience. */
export { screen, within, waitFor, act } from "@testing-library/react";
export { default as userEvent } from "@testing-library/user-event";