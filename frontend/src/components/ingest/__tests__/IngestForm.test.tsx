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
});
