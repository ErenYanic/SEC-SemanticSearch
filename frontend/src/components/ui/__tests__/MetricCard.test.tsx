import { render, screen } from "@testing-library/react";
import { FileText } from "lucide-react";
import { MetricCard } from "../MetricCard";

describe("MetricCard", () => {
  it("renders label and value", () => {
    render(<MetricCard icon={FileText} label="Filings" value={42} />);
    expect(screen.getByText("Filings")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders string value", () => {
    render(<MetricCard icon={FileText} label="Status" value="Active" />);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("renders icon", () => {
    const { container } = render(
      <MetricCard icon={FileText} label="Filings" value={10} />,
    );
    expect(container.querySelector("svg")).toBeTruthy();
  });

  it("shows capacity bar when capacity is provided", () => {
    render(
      <MetricCard
        icon={FileText}
        label="Filings"
        value={50}
        capacity={{ current: 50, max: 200 }}
      />,
    );
    expect(screen.getByText("50 / 200")).toBeInTheDocument();
  });

  it("calculates capacity percentage correctly", () => {
    const { container } = render(
      <MetricCard
        icon={FileText}
        label="Filings"
        value={75}
        capacity={{ current: 75, max: 100 }}
      />,
    );
    const fill = container.querySelector("[style]");
    expect(fill).toHaveStyle({ width: "75%" });
  });

  it("caps capacity at 100%", () => {
    const { container } = render(
      <MetricCard
        icon={FileText}
        label="Filings"
        value={150}
        capacity={{ current: 150, max: 100 }}
      />,
    );
    const fill = container.querySelector("[style]");
    expect(fill).toHaveStyle({ width: "100%" });
  });

  it("does not show capacity bar when not provided", () => {
    render(<MetricCard icon={FileText} label="Chunks" value={1000} />);
    expect(screen.queryByText(/\//)).not.toBeInTheDocument();
  });
});