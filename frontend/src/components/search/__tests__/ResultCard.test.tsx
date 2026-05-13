/**
 * Tests for ResultCard's parent-context display.
 *
 * The card now renders `parent_content` (the broader paragraph) and
 * wraps the matched `content` substring in a <mark> so analysts see
 * exactly which sentence(s) produced the vector match. These tests
 * cover the three branches the component can take:
 *
 *   1. parent_content present and contains content verbatim → render
 *      the parent with the chunk highlighted.
 *   2. parent_content present but missing the chunk text → fall back
 *      to plain parent text (no <mark>).
 *   3. parent_content absent → render the chunk text directly.
 */

import { render, screen } from "@testing-library/react";
import { ToastProvider } from "@/components/ui/Toast";
import { ResultCard } from "../ResultCard";
import type { SearchResult } from "@/lib/types";

function renderWithProviders(ui: React.ReactNode) {
  return render(<ToastProvider>{ui}</ToastProvider>);
}

const baseResult: SearchResult = {
  content: "chunk text",
  path: "Part II > Item 7",
  content_type: "text",
  ticker: "AAPL",
  form_type: "10-K",
  similarity: 0.55,
  filing_date: "2024-11-01",
  accession_number: "0000320193-24-000001",
  chunk_id: "AAPL_10-K_2024-11-01_001",
  segment_index: 4,
  parent_content: null,
};

describe("ResultCard parent-context display", () => {
  it("highlights the chunk inside the parent paragraph", () => {
    const result: SearchResult = {
      ...baseResult,
      parent_content:
        "Before context. chunk text in the middle. After context.",
    };
    renderWithProviders(
      <ResultCard result={result} rank={1} isExpanded />,
    );

    const mark = screen.getByTestId("chunk-highlight");
    // The <mark> must wrap exactly the chunk content — not the
    // surrounding sentences.
    expect(mark).toHaveTextContent("chunk text");
    expect(mark.tagName).toBe("MARK");

    // The broader paragraph context must also be on screen so the
    // analyst sees what surrounds the match.
    expect(screen.getByText(/Before context/)).toBeInTheDocument();
    expect(screen.getByText(/After context/)).toBeInTheDocument();
  });

  it("renders parent text without highlight when chunk is not a substring", () => {
    const result: SearchResult = {
      ...baseResult,
      content: "completely different wording",
      parent_content:
        "The parent paragraph does not contain the chunk verbatim.",
    };
    renderWithProviders(
      <ResultCard result={result} rank={1} isExpanded />,
    );
    expect(screen.queryByTestId("chunk-highlight")).not.toBeInTheDocument();
    expect(
      screen.getByText(/The parent paragraph does not contain/),
    ).toBeInTheDocument();
  });

  it("falls back to chunk text when parent_content is null (legacy)", () => {
    const result: SearchResult = {
      ...baseResult,
      content: "legacy chunk content",
      parent_content: null,
    };
    renderWithProviders(
      <ResultCard result={result} rank={1} isExpanded />,
    );
    expect(screen.queryByTestId("chunk-highlight")).not.toBeInTheDocument();
    expect(screen.getByText("legacy chunk content")).toBeInTheDocument();
  });
});
