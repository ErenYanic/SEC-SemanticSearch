/**
 * Page footer with version number.
 *
 * This is a Server Component (no "use client") — it has no
 * interactivity, so it renders as static HTML with zero JavaScript
 * sent to the browser.
 */

export function Footer() {
  return (
    <footer className="border-t border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950">
      <div className="mx-auto flex h-12 max-w-7xl items-center justify-center px-4 sm:px-6 lg:px-8">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          SEC Semantic Search
        </p>
      </div>
    </footer>
  );
}