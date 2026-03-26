import {
  renderWithProviders,
  screen,
  userEvent,
} from "@/test/utils";
import { IngestForm } from "../IngestForm";

const noop = () => {};

function renderForm(props: { onSubmit?: (req: unknown) => void; isSubmitting?: boolean } = {}) {
  return renderWithProviders(
    <IngestForm onSubmit={props.onSubmit ?? noop} isSubmitting={props.isSubmitting ?? false} />,
  );
}

describe("IngestForm", () => {
  // -------------------------------------------------------------------
  // BF-001: toggleFormType must not call addToast inside setFormTypes
  // -------------------------------------------------------------------

  it("shows a toast when attempting to deselect the last form type", async () => {
    const user = userEvent.setup();
    renderForm();

    // Both 10-K and 10-Q are active by default. Deselect 10-K first.
    const tenKButton = screen.getByRole("button", { name: "10-K" });
    const tenQButton = screen.getByRole("button", { name: "10-Q" });

    await user.click(tenKButton);

    // Now only 10-Q remains. Trying to deselect it should show the toast.
    await user.click(tenQButton);

    expect(
      screen.getByText("At least one form type must be selected."),
    ).toBeInTheDocument();
  });

  it("does not deselect the last remaining form type", async () => {
    const user = userEvent.setup();
    renderForm();

    const tenKButton = screen.getByRole("button", { name: "10-K" });
    const tenQButton = screen.getByRole("button", { name: "10-Q" });

    // Deselect 10-K — only 10-Q remains.
    await user.click(tenKButton);

    // Attempt to deselect 10-Q — should be blocked.
    await user.click(tenQButton);

    // 10-Q chip should still be in the active state (check via class).
    expect(tenQButton.className).toContain("bg-blue-100");
  });

  // -------------------------------------------------------------------
  // Ticker input
  // -------------------------------------------------------------------

  it("adds a ticker tag on Enter", async () => {
    const user = userEvent.setup();
    renderForm();

    const input = screen.getByPlaceholderText("Type a ticker and press Enter...");
    await user.type(input, "AAPL{Enter}");

    expect(screen.getByText("AAPL")).toBeInTheDocument();
  });

  it("removes a ticker tag via the remove button", async () => {
    const user = userEvent.setup();
    renderForm();

    const input = screen.getByPlaceholderText("Type a ticker and press Enter...");
    await user.type(input, "MSFT{Enter}");
    expect(screen.getByText("MSFT")).toBeInTheDocument();

    await user.click(screen.getByLabelText("Remove MSFT"));
    expect(screen.queryByText("MSFT")).not.toBeInTheDocument();
  });

  it("rejects duplicate tickers", async () => {
    const user = userEvent.setup();
    renderForm();

    const input = screen.getByPlaceholderText("Type a ticker and press Enter...");
    await user.type(input, "AAPL{Enter}");
    await user.type(input, "aapl{Enter}");

    // Only one AAPL tag should exist.
    const tags = screen.getAllByText("AAPL");
    expect(tags).toHaveLength(1);
  });

  // -------------------------------------------------------------------
  // Submit
  // -------------------------------------------------------------------

  it("disables submit when no tickers are entered", () => {
    renderForm();
    const submit = screen.getByRole("button", { name: /start ingestion/i });
    expect(submit).toBeDisabled();
  });

  it("calls onSubmit with a valid request", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    const input = screen.getByPlaceholderText("Type a ticker and press Enter...");
    await user.type(input, "AAPL{Enter}");

    await user.click(screen.getByRole("button", { name: /start ingestion/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const req = onSubmit.mock.calls[0][0];
    expect(req.tickers).toEqual(["AAPL"]);
    expect(req.form_types).toEqual(expect.arrayContaining(["10-K", "10-Q"]));
  });

  // -------------------------------------------------------------------
  // BF-008: 8-K form type support
  // -------------------------------------------------------------------

  it("renders the 8-K form type chip", () => {
    renderForm();
    expect(screen.getByRole("button", { name: "8-K" })).toBeInTheDocument();
  });

  it("does not include 8-K in defaults (opt-in only)", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    renderForm({ onSubmit });

    const tickerInput = screen.getByPlaceholderText("Type a ticker and press Enter...");
    await user.type(tickerInput, "AAPL{Enter}");
    await user.click(screen.getByRole("button", { name: /start ingestion/i }));

    const req = onSubmit.mock.calls[0][0];
    expect(req.form_types).not.toContain("8-K");
    expect(req.form_types).toEqual(expect.arrayContaining(["10-K", "10-Q"]));
  });

  it("includes 8-K when explicitly selected", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    renderForm({ onSubmit });

    const tickerInput = screen.getByPlaceholderText("Type a ticker and press Enter...");
    await user.type(tickerInput, "MSFT{Enter}");

    // Select 8-K
    await user.click(screen.getByRole("button", { name: "8-K" }));

    await user.click(screen.getByRole("button", { name: /start ingestion/i }));

    const req = onSubmit.mock.calls[0][0];
    expect(req.form_types).toContain("8-K");
  });

  // -------------------------------------------------------------------
  // BF-003: Count mode suppressed when date filters are active
  // -------------------------------------------------------------------

  it("hides count mode radio when a year filter is entered", async () => {
    const user = userEvent.setup();
    renderForm();

    // Count mode should be visible initially.
    expect(screen.getByText("Count mode")).toBeInTheDocument();

    // Open date filters and enter a year.
    await user.click(screen.getByRole("button", { name: /date filters/i }));
    const yearInput = screen.getByPlaceholderText("e.g. 2024");
    await user.type(yearInput, "2024");

    // Count mode radio should be replaced by the informational note.
    expect(screen.queryByText("Count mode")).not.toBeInTheDocument();
    expect(
      screen.getByText("When a date filter is active, all matching filings are fetched."),
    ).toBeInTheDocument();
  });

  it("hides count mode radio when a start date is entered", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.click(screen.getByRole("button", { name: /date filters/i }));
    const startDateInput = screen.getByLabelText("Start date");
    await user.type(startDateInput, "2023-01-01");

    expect(screen.queryByText("Count mode")).not.toBeInTheDocument();
    expect(
      screen.getByText("When a date filter is active, all matching filings are fetched."),
    ).toBeInTheDocument();
  });

  it("restores count mode radio when all date filters are cleared", async () => {
    const user = userEvent.setup();
    renderForm();

    // Activate a date filter.
    await user.click(screen.getByRole("button", { name: /date filters/i }));
    const yearInput = screen.getByPlaceholderText("e.g. 2024");
    await user.type(yearInput, "2024");

    expect(screen.queryByText("Count mode")).not.toBeInTheDocument();

    // Clear the year filter.
    await user.clear(yearInput);

    // Count mode should reappear.
    expect(screen.getByText("Count mode")).toBeInTheDocument();
  });

  it("submits count_mode 'latest' and no count when date filter is active", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    // Add a ticker.
    const tickerInput = screen.getByPlaceholderText("Type a ticker and press Enter...");
    await user.type(tickerInput, "AAPL{Enter}");

    // Switch to "total" count mode and set count before adding a date filter.
    await user.click(screen.getByLabelText(/total/i));
    // The count input should appear for total mode.
    const countInput = screen.getByPlaceholderText("e.g. 3");
    await user.type(countInput, "5");

    // Now activate a date filter — count mode should be suppressed.
    await user.click(screen.getByRole("button", { name: /date filters/i }));
    const yearInput = screen.getByPlaceholderText("e.g. 2024");
    await user.type(yearInput, "2023");

    // Submit.
    await user.click(screen.getByRole("button", { name: /start ingestion/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const req = onSubmit.mock.calls[0][0];
    expect(req.count_mode).toBe("latest");
    expect(req.count).toBeUndefined();
    expect(req.year).toBe(2023);
  });

  it("submits the selected count mode when no date filter is active", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    const tickerInput = screen.getByPlaceholderText("Type a ticker and press Enter...");
    await user.type(tickerInput, "MSFT{Enter}");

    // Select "per_form" mode and set count.  Use the exact label text to avoid
    // matching "Latest" (whose description contains "per form type per ticker").
    const perFormRadio = screen.getByDisplayValue("per_form");
    await user.click(perFormRadio);
    const countInput = screen.getByPlaceholderText("e.g. 3");
    await user.type(countInput, "2");

    await user.click(screen.getByRole("button", { name: /start ingestion/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const req = onSubmit.mock.calls[0][0];
    expect(req.count_mode).toBe("per_form");
    expect(req.count).toBe(2);
    expect(req.year).toBeUndefined();
  });
});
