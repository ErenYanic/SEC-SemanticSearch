import { render, screen } from "@testing-library/react";
import { Badge, taskStateToBadgeVariant } from "../Badge";

describe("Badge", () => {
  it("renders children", () => {
    render(<Badge>10-K</Badge>);
    expect(screen.getByText("10-K")).toBeInTheDocument();
  });

  it("applies gray variant by default", () => {
    render(<Badge>Default</Badge>);
    expect(screen.getByText("Default").className).toContain("bg-gray-100");
  });

  it.each([
    ["blue", "bg-blue-50"],
    ["green", "bg-green-50"],
    ["amber", "bg-amber-50"],
    ["red", "bg-red-50"],
  ] as const)("applies %s variant", (variant, expectedClass) => {
    render(<Badge variant={variant}>Label</Badge>);
    expect(screen.getByText("Label").className).toContain(expectedClass);
  });

  it("merges custom className", () => {
    render(<Badge className="extra">Tag</Badge>);
    expect(screen.getByText("Tag").className).toContain("extra");
  });

  it("renders as a span", () => {
    render(<Badge>Tag</Badge>);
    expect(screen.getByText("Tag").tagName).toBe("SPAN");
  });
});

describe("taskStateToBadgeVariant", () => {
  it.each([
    ["pending", "amber"],
    ["running", "blue"],
    ["completed", "green"],
    ["failed", "red"],
    ["cancelled", "red"],
  ] as const)("maps %s → %s", (state, expected) => {
    expect(taskStateToBadgeVariant(state)).toBe(expected);
  });
});