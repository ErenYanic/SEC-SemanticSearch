import { render, screen } from "@testing-library/react";
import { SimilarityBadge } from "../SimilarityBadge";

describe("SimilarityBadge", () => {
  it("displays percentage", () => {
    render(<SimilarityBadge similarity={0.45} />);
    expect(screen.getByText("45%")).toBeInTheDocument();
  });

  it("rounds to nearest integer", () => {
    render(<SimilarityBadge similarity={0.456} />);
    expect(screen.getByText("46%")).toBeInTheDocument();
  });

  it("renders green for similarity >= 0.40", () => {
    render(<SimilarityBadge similarity={0.4} />);
    expect(screen.getByText("40%").className).toContain("bg-green-50");
  });

  it("renders green for high similarity", () => {
    render(<SimilarityBadge similarity={0.85} />);
    expect(screen.getByText("85%").className).toContain("bg-green-50");
  });

  it("renders amber for similarity >= 0.25 and < 0.40", () => {
    render(<SimilarityBadge similarity={0.3} />);
    expect(screen.getByText("30%").className).toContain("bg-amber-50");
  });

  it("renders amber at the threshold boundary", () => {
    render(<SimilarityBadge similarity={0.25} />);
    expect(screen.getByText("25%").className).toContain("bg-amber-50");
  });

  it("renders red for similarity < 0.25", () => {
    render(<SimilarityBadge similarity={0.15} />);
    expect(screen.getByText("15%").className).toContain("bg-red-50");
  });

  it("renders red for very low similarity", () => {
    render(<SimilarityBadge similarity={0.05} />);
    expect(screen.getByText("5%").className).toContain("bg-red-50");
  });
});