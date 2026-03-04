/**
 * Global error boundary — catches unhandled errors in any route segment.
 *
 * ## Why `"use client"`?
 *
 * Next.js error boundaries **must** be Client Components. The framework
 * passes two props:
 *
 *   - `error` — the thrown Error instance (with `message` and `digest`)
 *   - `reset` — a function that re-renders the route segment, giving the
 *     page a chance to recover without a full reload
 *
 * ## Why `useEffect` for logging?
 *
 * `console.error` in the render path would fire on every re-render.
 * Logging in an effect ensures we capture the error exactly once per
 * boundary trigger, and it's the recommended Next.js pattern.
 */

"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { EmptyState, Button } from "@/components/ui";

interface ErrorPageProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  useEffect(() => {
    console.error("Unhandled error:", error);
  }, [error]);

  return (
    <EmptyState
      icon={AlertTriangle}
      title="Something went wrong"
      description={
        error.message || "An unexpected error occurred. Please try again."
      }
      action={<Button onClick={reset}>Try again</Button>}
    />
  );
}