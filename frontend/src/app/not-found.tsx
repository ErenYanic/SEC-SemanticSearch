/**
 * Custom 404 page — shown when no route matches the URL.
 *
 * ## Why a Server Component?
 *
 * This page has no hooks, no state, no event handlers. It's pure
 * markup rendered once. By keeping it as a Server Component (no
 * `"use client"`), zero JavaScript is sent to the browser for this
 * page — just the HTML.
 *
 * ## Why `EmptyState`?
 *
 * The `EmptyState` component (icon + title + description + action)
 * is our standard pattern for "nothing to show" pages. Reusing it
 * here keeps the visual language consistent across error states,
 * empty databases, and missing routes.
 */

import Link from "next/link";
import { FileQuestion } from "lucide-react";
import { EmptyState, Button } from "@/components/ui";

export default function NotFound() {
  return (
    <EmptyState
      icon={FileQuestion}
      title="Page not found"
      description="The page you're looking for doesn't exist or has been moved."
      action={
        <Link href="/">
          <Button>Go to Dashboard</Button>
        </Link>
      }
    />
  );
}