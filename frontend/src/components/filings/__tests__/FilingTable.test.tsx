import { renderWithProviders, screen } from "@/test/utils";
import { FilingTable } from "../FilingTable";
import type { Filing } from "@/lib/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const FILING: Filing = {
  ticker: "AAPL",
  form_type: "10-K",
  filing_date: "2024-01-15",
  accession_number: "0000320193-24-000006",
  chunk_count: 42,
  ingested_at: "2024-02-01T12:00:00Z",
};

const noop = () => {};

function renderTable(filings: Filing[] = [FILING]) {
  return renderWithProviders(
    <FilingTable
      filings={filings}
      sortBy="filing_date"
      order="desc"
      onSortChange={noop}
      selected={new Set()}
      onSelectionChange={noop}
      onDeleteFiling={noop}
      isDeleting={false}
    />,
  );
}

// ---------------------------------------------------------------------------
// BF-007: Accession number column
// ---------------------------------------------------------------------------

describe("FilingTable — Accession column (BF-007)", () => {
  it("renders the Accession No. column header", () => {
    renderTable();
    expect(screen.getByText("Accession No.")).toBeInTheDocument();
  });

  it("displays the accession number in the row", () => {
    renderTable();
    expect(screen.getByText("0000320193-24-000006")).toBeInTheDocument();
  });

  it("renders the accession number in monospace font", () => {
    renderTable();
    const accessionEl = screen.getByText("0000320193-24-000006");
    expect(accessionEl.className).toContain("font-mono");
  });

  it("renders a copy button with aria-label for each filing", () => {
    renderTable();
    expect(
      screen.getByRole("button", {
        name: "Copy accession number 0000320193-24-000006",
      }),
    ).toBeInTheDocument();
  });

  it("accession column is not sortable (no button in header)", () => {
    renderTable();
    const headerText = screen.getByText("Accession No.");
    // The header text should be plain text, not wrapped in a button
    expect(headerText.tagName).not.toBe("BUTTON");
    expect(headerText.closest("button")).toBeNull();
  });
});
