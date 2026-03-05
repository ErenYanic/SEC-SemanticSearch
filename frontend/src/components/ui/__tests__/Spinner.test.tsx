import { render, screen } from "@testing-library/react";
import { Spinner, FullPageSpinner } from "../Spinner";

describe("Spinner", () => {
  it("has role=status for accessibility", () => {
    render(<Spinner />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("has aria-label for screen readers", () => {
    render(<Spinner />);
    expect(screen.getByLabelText("Loading")).toBeInTheDocument();
  });

  it("applies medium size by default", () => {
    const { container } = render(<Spinner />);
    const svg = container.querySelector("svg");
    expect(svg!.classList.toString()).toContain("h-5");
    expect(svg!.classList.toString()).toContain("w-5");
  });

  it("applies small size", () => {
    const { container } = render(<Spinner size="sm" />);
    const svg = container.querySelector("svg");
    expect(svg!.classList.toString()).toContain("h-4");
    expect(svg!.classList.toString()).toContain("w-4");
  });

  it("applies large size", () => {
    const { container } = render(<Spinner size="lg" />);
    const svg = container.querySelector("svg");
    expect(svg!.classList.toString()).toContain("h-8");
    expect(svg!.classList.toString()).toContain("w-8");
  });

  it("applies extra large size", () => {
    const { container } = render(<Spinner size="xl" />);
    const svg = container.querySelector("svg");
    expect(svg!.classList.toString()).toContain("h-12");
    expect(svg!.classList.toString()).toContain("w-12");
  });

  it("has animate-spin class", () => {
    const { container } = render(<Spinner />);
    const svg = container.querySelector("svg");
    expect(svg!.classList.toString()).toContain("animate-spin");
  });
});

describe("FullPageSpinner", () => {
  it("renders a Spinner inside a centred container", () => {
    render(<FullPageSpinner />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("uses xl size", () => {
    const { container } = render(<FullPageSpinner />);
    const svg = container.querySelector("svg");
    expect(svg!.classList.toString()).toContain("h-12");
  });
});