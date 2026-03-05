import { render, screen } from "@testing-library/react";
import { AlertTriangle } from "lucide-react";
import { EmptyState } from "../EmptyState";

describe("EmptyState", () => {
  it("renders title", () => {
    render(<EmptyState icon={AlertTriangle} title="No results" />);
    expect(screen.getByText("No results")).toBeInTheDocument();
  });

  it("renders description when provided", () => {
    render(
      <EmptyState
        icon={AlertTriangle}
        title="Empty"
        description="Try adjusting your filters."
      />,
    );
    expect(screen.getByText("Try adjusting your filters.")).toBeInTheDocument();
  });

  it("does not render description when omitted", () => {
    const { container } = render(
      <EmptyState icon={AlertTriangle} title="Empty" />,
    );
    // Only the title text, no <p> for description
    const paragraphs = container.querySelectorAll("p");
    expect(paragraphs).toHaveLength(0);
  });

  it("renders action when provided", () => {
    render(
      <EmptyState
        icon={AlertTriangle}
        title="Empty"
        action={<button>Retry</button>}
      />,
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("does not render action wrapper when omitted", () => {
    const { container } = render(
      <EmptyState icon={AlertTriangle} title="Empty" />,
    );
    // Should only have icon container and title — no action div
    expect(container.querySelectorAll("button")).toHaveLength(0);
  });

  it("renders the icon", () => {
    const { container } = render(
      <EmptyState icon={AlertTriangle} title="Error" />,
    );
    const svg = container.querySelector("svg");
    expect(svg).toBeTruthy();
  });
});