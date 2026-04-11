import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "@/components/ui/Toast";
import type { ReactNode } from "react";
import DashboardPage from "../page";

// Mock hooks at the hook level — don't let tests hit the API layer
vi.mock("@/hooks/useStatus");
import { useStatus } from "@/hooks/useStatus";
const mockUseStatus = vi.mocked(useStatus);

// Mock next/link and next/navigation
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/",
}));

// Mock recharts to avoid canvas/SVG rendering issues in jsdom
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
}));

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}

describe("DashboardPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows skeleton while loading", () => {
    mockUseStatus.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useStatus>);

    const { container } = render(<DashboardPage />, { wrapper });
    // Skeleton uses shimmer animation (Tailwind arbitrary value syntax)
    expect(container.innerHTML).toContain("shimmer");
  });

  it("shows error state when API fails", () => {
    mockUseStatus.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("Connection refused"),
    } as ReturnType<typeof useStatus>);

    render(<DashboardPage />, { wrapper });
    expect(screen.getByText("Unable to load dashboard")).toBeInTheDocument();
  });

  it("shows empty state when no filings exist", () => {
    mockUseStatus.mockReturnValue({
      data: {
        filing_count: 0,
        max_filings: 200,
        chunk_count: 0,
        tickers: [],
        form_breakdown: {},
        ticker_breakdown: [],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useStatus>);

    render(<DashboardPage />, { wrapper });
    expect(screen.getByText("No filings yet")).toBeInTheDocument();
    expect(screen.getByText("Ingest Filings")).toBeInTheDocument();
  });

  it("renders dashboard with data", () => {
    mockUseStatus.mockReturnValue({
      data: {
        filing_count: 5,
        max_filings: 200,
        chunk_count: 1500,
        tickers: ["AAPL", "MSFT"],
        form_breakdown: { "10-K": 3, "10-Q": 2 },
        ticker_breakdown: [
          { ticker: "AAPL", filings: 3, chunks: 900, forms: ["10-K", "10-Q"] },
          { ticker: "MSFT", filings: 2, chunks: 600, forms: ["10-K"] },
        ],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useStatus>);

    render(<DashboardPage />, { wrapper });
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    // Filing count "5" appears in both the KPI card and the header
    // meta strip — at least one match confirms render.
    expect(screen.getAllByText("5").length).toBeGreaterThan(0);
    // Chunk count is formatted via toLocaleString() — locale varies in jsdom
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("MSFT")).toBeInTheDocument();
  });
});