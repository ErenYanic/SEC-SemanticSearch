import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Modal } from "../Modal";

/**
 * The Modal renders inside a backdrop with `aria-hidden="true"` (the
 * backdrop itself is decorative). This means `getByRole("dialog")`
 * won't find it unless we pass `{ hidden: true }`. Similarly, buttons
 * inside the dialog are hidden from the default accessibility tree
 * query. We use `getByRole("button", { hidden: true })` throughout.
 */

describe("Modal", () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
    onConfirm: vi.fn(),
    title: "Confirm Delete",
    children: "Are you sure you want to delete this filing?",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders title and body when open", () => {
    render(<Modal {...defaultProps} />);
    expect(screen.getByText("Confirm Delete")).toBeInTheDocument();
    expect(screen.getByText("Are you sure you want to delete this filing?")).toBeInTheDocument();
  });

  it("renders nothing when closed", () => {
    render(<Modal {...defaultProps} open={false} />);
    expect(screen.queryByText("Confirm Delete")).not.toBeInTheDocument();
  });

  it("has dialog role and aria-modal", () => {
    render(<Modal {...defaultProps} />);
    const dialog = screen.getByRole("dialog", { hidden: true });
    expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  it("connects aria-labelledby to title", () => {
    render(<Modal {...defaultProps} />);
    const dialog = screen.getByRole("dialog", { hidden: true });
    const labelledBy = dialog.getAttribute("aria-labelledby");
    expect(labelledBy).toBeTruthy();
    const title = document.getElementById(labelledBy!);
    expect(title).toHaveTextContent("Confirm Delete");
  });

  it("renders Cancel and Confirm buttons", () => {
    render(<Modal {...defaultProps} />);
    expect(screen.getByRole("button", { name: "Cancel", hidden: true })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm", hidden: true })).toBeInTheDocument();
  });

  it("uses custom confirm label", () => {
    render(<Modal {...defaultProps} confirmLabel="Delete Forever" />);
    expect(screen.getByRole("button", { name: "Delete Forever", hidden: true })).toBeInTheDocument();
  });

  it("calls onClose when Cancel is clicked", async () => {
    const user = userEvent.setup();
    render(<Modal {...defaultProps} />);
    await user.click(screen.getByRole("button", { name: "Cancel", hidden: true }));
    expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onConfirm when Confirm is clicked", async () => {
    const user = userEvent.setup();
    render(<Modal {...defaultProps} />);
    await user.click(screen.getByRole("button", { name: "Confirm", hidden: true }));
    expect(defaultProps.onConfirm).toHaveBeenCalledTimes(1);
  });

  it("calls onClose on Escape key", async () => {
    const user = userEvent.setup();
    render(<Modal {...defaultProps} />);
    await user.keyboard("{Escape}");
    expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
  });

  it("disables confirm button when confirmDisabled is true", () => {
    render(<Modal {...defaultProps} confirmDisabled />);
    expect(screen.getByRole("button", { name: "Confirm", hidden: true })).toBeDisabled();
  });

  it("shows loading state on confirm button", () => {
    render(<Modal {...defaultProps} confirmLoading />);
    const confirmBtn = screen.getByRole("button", { name: "Confirm", hidden: true });
    expect(confirmBtn).toBeDisabled();
    expect(confirmBtn).toHaveAttribute("aria-busy", "true");
  });
});