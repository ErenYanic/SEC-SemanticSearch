import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useFilings, DEFAULT_QUERY_PARAMS } from "../useFilings";

vi.mock("@/lib/api", () => ({
  getFilings: vi.fn(),
  deleteFiling: vi.fn(),
  deleteFilingsByIds: vi.fn(),
  clearAllFilings: vi.fn(),
}));

import { getFilings, deleteFiling, deleteFilingsByIds, clearAllFilings } from "@/lib/api";
const mockGetFilings = vi.mocked(getFilings);
const mockDeleteFiling = vi.mocked(deleteFiling);
const mockDeleteFilingsByIds = vi.mocked(deleteFilingsByIds);
const mockClearAllFilings = vi.mocked(clearAllFilings);

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

const MOCK_FILINGS = {
  filings: [
    {
      ticker: "AAPL",
      form_type: "10-K",
      filing_date: "2024-01-15",
      accession_number: "0001-24-000001",
      chunk_count: 120,
      ingested_at: "2024-06-01T12:00:00Z",
    },
    {
      ticker: "MSFT",
      form_type: "10-Q",
      filing_date: "2024-03-20",
      accession_number: "0002-24-000002",
      chunk_count: 80,
      ingested_at: "2024-06-02T12:00:00Z",
    },
  ],
  total: 2,
};

describe("useFilings", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("fetches filings with default params", async () => {
    mockGetFilings.mockResolvedValue(MOCK_FILINGS);

    const { result } = renderHook(() => useFilings(DEFAULT_QUERY_PARAMS), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.filings).toHaveLength(2);
    expect(result.current.total).toBe(2);
    expect(mockGetFilings).toHaveBeenCalledWith({
      ticker: undefined,
      form_type: undefined,
      sort_by: "filing_date",
      order: "desc",
    });
  });

  it("passes ticker and form_type filters to API", async () => {
    mockGetFilings.mockResolvedValue({ filings: [], total: 0 });

    const params = { ticker: "AAPL", formType: "10-K", sortBy: "ticker" as const, order: "asc" as const };
    const { result } = renderHook(() => useFilings(params), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(mockGetFilings).toHaveBeenCalledWith({
      ticker: "AAPL",
      form_type: "10-K",
      sort_by: "ticker",
      order: "asc",
    });
  });

  it("defaults to empty array when data is undefined", () => {
    mockGetFilings.mockReturnValue(new Promise(() => {})); // never resolves

    const { result } = renderHook(() => useFilings(DEFAULT_QUERY_PARAMS), {
      wrapper: createWrapper(),
    });

    expect(result.current.filings).toEqual([]);
    expect(result.current.total).toBe(0);
    expect(result.current.isLoading).toBe(true);
  });

  it("reports error state on fetch failure", async () => {
    mockGetFilings.mockRejectedValue(new Error("Server error"));

    const { result } = renderHook(() => useFilings(DEFAULT_QUERY_PARAMS), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Server error");
  });

  it("deleteSingle removes filing from cache optimistically", async () => {
    mockGetFilings.mockResolvedValue(MOCK_FILINGS);
    mockDeleteFiling.mockResolvedValue({ accession_number: "0001-24-000001", chunks_deleted: 120 });

    const { result } = renderHook(() => useFilings(DEFAULT_QUERY_PARAMS), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.filings).toHaveLength(2));

    await act(async () => {
      await result.current.deleteSingle("0001-24-000001");
    });

    await waitFor(() => expect(result.current.filings).toHaveLength(1));
    expect(result.current.filings[0].accession_number).toBe("0002-24-000002");
  });

  it("deleteSelected removes multiple filings in a single batch request", async () => {
    mockGetFilings.mockResolvedValue(MOCK_FILINGS);
    mockDeleteFilingsByIds.mockResolvedValue({
      filings_deleted: 2,
      chunks_deleted: 200,
      not_found: [],
    });

    const { result } = renderHook(() => useFilings(DEFAULT_QUERY_PARAMS), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.filings).toHaveLength(2));

    await act(async () => {
      const response = await result.current.deleteSelected(["0001-24-000001", "0002-24-000002"]);
      expect(response.filings_deleted).toBe(2);
    });

    await waitFor(() => expect(result.current.filings).toHaveLength(0));
    expect(mockDeleteFilingsByIds).toHaveBeenCalledTimes(1);
    expect(mockDeleteFilingsByIds.mock.calls[0][0]).toEqual(["0001-24-000001", "0002-24-000002"]);
  });

  it("clearAll sets cache to empty", async () => {
    mockGetFilings.mockResolvedValue(MOCK_FILINGS);
    mockClearAllFilings.mockResolvedValue({ filings_deleted: 2, chunks_deleted: 200 });

    const { result } = renderHook(() => useFilings(DEFAULT_QUERY_PARAMS), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.filings).toHaveLength(2));

    await act(async () => {
      await result.current.clearAll();
    });

    await waitFor(() => expect(result.current.filings).toHaveLength(0));
    expect(result.current.total).toBe(0);
  });

  it("isDeleting is true during delete mutation", async () => {
    mockGetFilings.mockResolvedValue(MOCK_FILINGS);

    let resolveDelete: (value: { accession_number: string; chunks_deleted: number }) => void;
    mockDeleteFiling.mockImplementation(
      () => new Promise((resolve) => { resolveDelete = resolve; }),
    );

    const { result } = renderHook(() => useFilings(DEFAULT_QUERY_PARAMS), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.filings).toHaveLength(2));

    act(() => {
      result.current.deleteSingle("0001-24-000001");
    });

    await waitFor(() => expect(result.current.isDeleting).toBe(true));

    await act(async () => {
      resolveDelete!({ accession_number: "0001-24-000001", chunks_deleted: 120 });
    });

    await waitFor(() => expect(result.current.isDeleting).toBe(false));
  });
});