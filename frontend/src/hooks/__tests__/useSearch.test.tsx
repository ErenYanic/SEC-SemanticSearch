import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useSearch } from "../useSearch";

vi.mock("@/lib/api", () => ({
  search: vi.fn(),
}));

import { search } from "@/lib/api";
const mockSearch = vi.mocked(search);

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

describe("useSearch", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("starts idle with no data", () => {
    const { result } = renderHook(() => useSearch(), {
      wrapper: createWrapper(),
    });

    expect(result.current.data).toBeUndefined();
    expect(result.current.isPending).toBe(false);
  });

  it("returns search results on mutate", async () => {
    const mockResponse = {
      query: "revenue growth",
      results: [
        {
          content: "Revenue grew 15%",
          similarity: 0.45,
          ticker: "AAPL",
          form_type: "10-K",
          content_type: "text" as const,
          path: "Part II > Item 7",
          filing_date: "2024-01-15",
          accession_number: "0001-24-000001",
        },
      ],
      total_results: 1,
      search_time_ms: 42,
    };
    mockSearch.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useSearch(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.mutate({ query: "revenue growth", top_k: 5 });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockResponse);
    // React Query passes the variables as first arg, plus internal context
    expect(mockSearch).toHaveBeenCalledWith(
      { query: "revenue growth", top_k: 5 },
      expect.anything(),
    );
  });

  it("handles search error", async () => {
    mockSearch.mockRejectedValue(new Error("Search failed"));

    const { result } = renderHook(() => useSearch(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.mutate({ query: "test" });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Search failed");
  });
});