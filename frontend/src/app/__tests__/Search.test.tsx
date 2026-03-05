import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "@/components/ui/Toast";
import type { ReactNode } from "react";
import SearchPage from "../search/page";

// Mock hooks
vi.mock("@/hooks/useStatus");
vi.mock("@/hooks/useSearch");

import { useStatus } from "@/hooks/useStatus";
import { useSearch } from "@/hooks/useSearch";
const mockUseStatus = vi.mocked(useStatus);
const mockUseSearch = vi.mocked(useSearch);

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
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

const defaultSearchReturn = {
  mutate: vi.fn(),
  data: undefined,
  isPending: false,
  isError: false,
  error: null,
  isSuccess: false,
  reset: vi.fn(),
} as unknown as ReturnType<typeof useSearch>;

describe("SearchPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows skeleton while status is loading", () => {
    mockUseStatus.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof useStatus>);
    mockUseSearch.mockReturnValue(defaultSearchReturn);

    const { container } = render(<SearchPage />, { wrapper });
    expect(container.innerHTML).toContain("shimmer");
  });

  it("shows empty state when no filings to search", () => {
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
    mockUseSearch.mockReturnValue(defaultSearchReturn);

    render(<SearchPage />, { wrapper });
    expect(screen.getByText("No filings to search")).toBeInTheDocument();
  });

  it("renders search bar when data is available", () => {
    mockUseStatus.mockReturnValue({
      data: {
        filing_count: 5,
        max_filings: 200,
        chunk_count: 1500,
        tickers: ["AAPL"],
        form_breakdown: { "10-K": 5 },
        ticker_breakdown: [],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useStatus>);
    mockUseSearch.mockReturnValue(defaultSearchReturn);

    render(<SearchPage />, { wrapper });
    expect(screen.getByRole("heading", { name: "Search" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("calls mutate on form submission", async () => {
    const mutateFn = vi.fn();
    mockUseStatus.mockReturnValue({
      data: {
        filing_count: 5,
        max_filings: 200,
        chunk_count: 1500,
        tickers: ["AAPL"],
        form_breakdown: { "10-K": 5 },
        ticker_breakdown: [],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useStatus>);
    mockUseSearch.mockReturnValue({
      ...defaultSearchReturn,
      mutate: mutateFn,
    } as unknown as ReturnType<typeof useSearch>);

    const user = userEvent.setup();
    render(<SearchPage />, { wrapper });

    const input = screen.getByPlaceholderText(/search/i);
    await user.type(input, "revenue growth");
    await user.keyboard("{Enter}");

    expect(mutateFn).toHaveBeenCalledWith(
      expect.objectContaining({ query: "revenue growth" }),
    );
  });
});