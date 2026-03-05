import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider, useToast } from "../Toast";

/** Helper component that triggers a toast on click. */
function ToastTrigger({ variant = "success" as const, message = "Done!" }) {
  const { addToast } = useToast();
  return (
    <button onClick={() => addToast(variant, message)}>
      Trigger
    </button>
  );
}

function renderWithToast(ui: React.ReactElement) {
  return render(<ToastProvider>{ui}</ToastProvider>);
}

describe("Toast system", () => {
  it("renders a toast when addToast is called", async () => {
    const user = userEvent.setup();
    renderWithToast(<ToastTrigger message="File deleted" />);

    await user.click(screen.getByText("Trigger"));

    expect(screen.getByText("File deleted")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("auto-dismisses after timeout", () => {
    vi.useFakeTimers();

    function AutoDismissTest() {
      const { addToast } = useToast();
      return (
        <button onClick={() => addToast("success", "Temporary")}>
          Add
        </button>
      );
    }

    renderWithToast(<AutoDismissTest />);

    // Use fireEvent (click()) instead of userEvent to avoid fake timer conflicts
    act(() => {
      screen.getByText("Add").click();
    });

    expect(screen.getByText("Temporary")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(screen.queryByText("Temporary")).not.toBeInTheDocument();

    vi.useRealTimers();
  });

  it("can be dismissed manually", async () => {
    const user = userEvent.setup();
    renderWithToast(<ToastTrigger message="Dismiss me" />);

    await user.click(screen.getByText("Trigger"));
    expect(screen.getByText("Dismiss me")).toBeInTheDocument();

    await user.click(screen.getByLabelText("Dismiss notification"));
    expect(screen.queryByText("Dismiss me")).not.toBeInTheDocument();
  });

  it("shows at most 5 toasts", () => {
    function MultiTrigger() {
      const { addToast } = useToast();
      return (
        <button onClick={() => {
          for (let i = 1; i <= 7; i++) {
            addToast("info", `Toast ${i}`);
          }
        }}>
          Add Many
        </button>
      );
    }

    renderWithToast(<MultiTrigger />);

    act(() => {
      screen.getByText("Add Many").click();
    });

    const alerts = screen.getAllByRole("alert");
    expect(alerts).toHaveLength(5);
    expect(screen.queryByText("Toast 1")).not.toBeInTheDocument();
    expect(screen.queryByText("Toast 2")).not.toBeInTheDocument();
    expect(screen.getByText("Toast 3")).toBeInTheDocument();
    expect(screen.getByText("Toast 7")).toBeInTheDocument();
  });

  it("renders different variants", async () => {
    const user = userEvent.setup();

    function VariantTriggers() {
      const { addToast } = useToast();
      return (
        <>
          <button onClick={() => addToast("success", "Success!")}>S</button>
          <button onClick={() => addToast("error", "Error!")}>E</button>
          <button onClick={() => addToast("info", "Info!")}>I</button>
        </>
      );
    }

    renderWithToast(<VariantTriggers />);

    await user.click(screen.getByText("S"));
    await user.click(screen.getByText("E"));
    await user.click(screen.getByText("I"));

    expect(screen.getByText("Success!")).toBeInTheDocument();
    expect(screen.getByText("Error!")).toBeInTheDocument();
    expect(screen.getByText("Info!")).toBeInTheDocument();
  });

  it("throws when useToast is called outside provider", () => {
    function Orphan() {
      useToast();
      return null;
    }

    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Orphan />)).toThrow(
      "useToast() must be used within a <ToastProvider>"
    );
    spy.mockRestore();
  });
});