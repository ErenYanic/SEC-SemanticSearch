"use client";

/**
 * Top navigation bar — present on every page.
 *
 * Layout:
 *   [GitHub icon]  SEC Semantic Search  |  Dashboard  Search  Ingest  Filings  |  [task indicator]  [theme toggle]
 *
 * "use client" is required because we use `usePathname()` (a React
 * hook) to highlight the active navigation link, and `useTheme()` to
 * toggle dark/light mode.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Github, LayoutDashboard, Search, Upload, FileText, Sun, Moon, Loader2 } from "lucide-react";
import { useTheme } from "./ThemeProvider";

// ---------------------------------------------------------------------------
// Navigation items
// ---------------------------------------------------------------------------

/**
 * Each nav item maps a URL path to a label and icon.
 *
 * We define this as a const array so the navbar and active-link
 * logic share a single source of truth.
 */
const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/search", label: "Search", icon: Search },
  { href: "/ingest", label: "Ingest", icon: Upload },
  { href: "/filings", label: "Filings", icon: FileText },
] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Props for the Navbar.
 *
 * `isTaskActive` is passed from the layout (which will poll for
 * active tasks via React Query in W3).  For now it defaults to false.
 */
interface NavbarProps {
  isTaskActive?: boolean;
}

export function Navbar({ isTaskActive = false }: NavbarProps) {
  // `usePathname()` returns the current URL path, e.g. "/search".
  // We use it to determine which nav link should be highlighted.
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();

  return (
    <nav className="border-b border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950">
      <div className="mx-auto flex h-16 max-w-7xl items-center px-4 sm:px-6 lg:px-8">

        {/* ---- Left: GitHub link + app title ---- */}
        <div className="flex items-center gap-3">
          <a
            href="https://github.com/ErenYanic/SEC-SemanticSearch"
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-500 transition-colors hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
            aria-label="GitHub repository"
          >
            <Github className="h-6 w-6" />
          </a>
          <Link
            href="/"
            className="text-lg font-semibold text-gray-900 dark:text-gray-100"
          >
            SEC Semantic Search
          </Link>
        </div>

        {/* ---- Centre: navigation links ---- */}
        <div className="ml-10 flex items-center gap-1">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            // A link is "active" when the pathname matches exactly
            // (for "/") or starts with the href (for "/search", etc.).
            const isActive =
              href === "/" ? pathname === "/" : pathname.startsWith(href);

            return (
              <Link
                key={href}
                href={href}
                className={`
                  flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors
                  ${
                    isActive
                      ? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                      : "text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-100"
                  }
                `}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
        </div>

        {/* ---- Right: active task indicator + theme toggle ---- */}
        <div className="ml-auto flex items-center gap-3">

          {/* Active task indicator — only visible when a task is running */}
          {isTaskActive && (
            <div className="flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700 dark:bg-blue-950 dark:text-blue-300">
              {/* Loader2 has a built-in spin animation via CSS */}
              <Loader2 className="h-4 w-4 animate-spin" />
              Ingesting...
            </div>
          )}

          {/* Theme toggle button */}
          <button
            onClick={toggleTheme}
            className="rounded-md p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-100"
            aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
          >
            {theme === "light" ? (
              <Moon className="h-5 w-5" />
            ) : (
              <Sun className="h-5 w-5" />
            )}
          </button>
        </div>
      </div>
    </nav>
  );
}