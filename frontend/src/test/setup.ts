/**
 * Vitest setup file — runs before every test file.
 *
 * Imports `@testing-library/jest-dom/vitest` which adds custom matchers
 * like `toBeInTheDocument()`, `toHaveTextContent()`, `toBeDisabled()`,
 * etc. to Vitest's `expect`. These matchers make DOM assertions more
 * readable than raw DOM property checks.
 */

import "@testing-library/jest-dom/vitest";