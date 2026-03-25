import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  SearchFilters,
  DEFAULT_FILTERS,
  countActiveFilters,
  type SearchFilterValues,
} from "../SearchFilters";

// ---------------------------------------------------------------------------
// countActiveFilters unit tests
// ---------------------------------------------------------------------------

describe("countActiveFilters", () => {
  it("returns 0 for defaults", () => {
    expect(countActiveFilters(DEFAULT_FILTERS)).toBe(0);
  });

  it("counts tickers as one filter regardless of count", () => {
    expect(
      countActiveFilters({ ...DEFAULT_FILTERS, tickers: ["AAPL", "MSFT"] }),
    ).toBe(1);
  });

  it("counts form types as one filter", () => {
    expect(
      countActiveFilters({ ...DEFAULT_FILTERS, formTypes: ["10-K"] }),
    ).toBe(1);
  });

  it("counts accession numbers as one filter", () => {
    expect(
      countActiveFilters({
        ...DEFAULT_FILTERS,
        accessionNumbers: ["0000320193-24-000001"],
      }),
    ).toBe(1);
  });

  it("counts multiple active filters", () => {
    expect(
      countActiveFilters({
        tickers: ["AAPL"],
        formTypes: ["10-K"],
        topK: 10,
        minSimilarity: 0.5,
        accessionNumbers: ["ACC-001"],
      }),
    ).toBe(5);
  });
});

// ---------------------------------------------------------------------------
// SearchFilters component tests
// ---------------------------------------------------------------------------

describe("SearchFilters", () => {
  const availableTickers = ["AAPL", "MSFT", "GOOGL"];

  function renderFilters(
    overrides: Partial<SearchFilterValues> = {},
    onChange = vi.fn(),
  ) {
    const filters = { ...DEFAULT_FILTERS, ...overrides };
    return {
      onChange,
      ...render(
        <SearchFilters
          filters={filters}
          onFiltersChange={onChange}
          availableTickers={availableTickers}
        />,
      ),
    };
  }

  it("renders the Filters toggle button", () => {
    renderFilters();
    expect(screen.getByRole("button", { name: /filters/i })).toBeInTheDocument();
  });

  it("shows the filter panel when toggle is clicked", async () => {
    const user = userEvent.setup();
    renderFilters();

    await user.click(screen.getByRole("button", { name: /filters/i }));

    expect(screen.getByRole("region", { name: /search filters/i })).toBeInTheDocument();
  });

  it("renders ticker chips when panel is open", async () => {
    const user = userEvent.setup();
    renderFilters();

    await user.click(screen.getByRole("button", { name: /filters/i }));

    for (const t of availableTickers) {
      expect(screen.getByRole("button", { name: t })).toBeInTheDocument();
    }
  });

  it("toggles a ticker chip on click", async () => {
    const user = userEvent.setup();
    const { onChange } = renderFilters();

    await user.click(screen.getByRole("button", { name: /filters/i }));
    await user.click(screen.getByRole("button", { name: "AAPL" }));

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ tickers: ["AAPL"] }),
    );
  });

  it("removes a ticker chip on second click", async () => {
    const user = userEvent.setup();
    const { onChange } = renderFilters({ tickers: ["AAPL"] });

    await user.click(screen.getByRole("button", { name: /filters/i }));
    await user.click(screen.getByRole("button", { name: /AAPL/i }));

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ tickers: [] }),
    );
  });

  it("renders form type chips and toggles them", async () => {
    const user = userEvent.setup();
    const { onChange } = renderFilters();

    await user.click(screen.getByRole("button", { name: /filters/i }));
    await user.click(screen.getByRole("button", { name: "10-K" }));

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ formTypes: ["10-K"] }),
    );
  });

  it("selects multiple form types", async () => {
    const user = userEvent.setup();
    const { onChange } = renderFilters({ formTypes: ["10-K"] });

    await user.click(screen.getByRole("button", { name: /filters/i }));
    await user.click(screen.getByRole("button", { name: "10-Q" }));

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ formTypes: ["10-K", "10-Q"] }),
    );
  });

  it("shows active filter count badge", () => {
    renderFilters({ tickers: ["AAPL"], formTypes: ["10-K"] });

    // Badge should show 2 active filters
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("clears all filters when Clear button is clicked", async () => {
    const user = userEvent.setup();
    const { onChange } = renderFilters({
      tickers: ["AAPL"],
      formTypes: ["10-K"],
    });

    await user.click(screen.getByRole("button", { name: /clear/i }));

    expect(onChange).toHaveBeenCalledWith(DEFAULT_FILTERS);
  });

  it("handles comma-separated accession numbers", async () => {
    const user = userEvent.setup();
    const { onChange } = renderFilters();

    await user.click(screen.getByRole("button", { name: /filters/i }));
    const input = screen.getByPlaceholderText(/0000320193/);

    // Paste the full value to avoid keystroke-by-keystroke issues
    await user.clear(input);
    await user.click(input);
    await user.paste("0000320193-24-000123, 0000320193-24-000456");

    // onChange is called on paste; check the final call
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall.accessionNumbers).toEqual([
      "0000320193-24-000123",
      "0000320193-24-000456",
    ]);
  });
});
