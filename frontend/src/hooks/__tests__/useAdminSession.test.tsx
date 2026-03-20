import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useAdminSession } from "../useAdminSession";

vi.mock("@/lib/api", () => ({
  getAdminSession: vi.fn(),
  loginAdminSession: vi.fn(),
  logoutAdminSession: vi.fn(),
}));

import {
  getAdminSession,
  loginAdminSession,
  logoutAdminSession,
} from "@/lib/api";

const mockGetAdminSession = vi.mocked(getAdminSession);
const mockLoginAdminSession = vi.mocked(loginAdminSession);
const mockLogoutAdminSession = vi.mocked(logoutAdminSession);

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  return Wrapper;
}

describe("useAdminSession", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("returns the current admin session state", async () => {
    mockGetAdminSession.mockResolvedValue({
      admin_required: true,
      is_admin: false,
    });

    const { result } = renderHook(() => useAdminSession(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.adminRequired).toBe(true);
    expect(result.current.isAdmin).toBe(false);
  });

  it("refreshes session state after login", async () => {
    mockGetAdminSession
      .mockResolvedValueOnce({ admin_required: true, is_admin: false })
      .mockResolvedValueOnce({ admin_required: true, is_admin: true });
    mockLoginAdminSession.mockResolvedValue();

    const { result } = renderHook(() => useAdminSession(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.login("secret-admin");
    });

    await waitFor(() => expect(result.current.isAdmin).toBe(true));
    expect(mockLoginAdminSession.mock.calls[0]?.[0]).toBe("secret-admin");
  });

  it("refreshes session state after logout", async () => {
    mockGetAdminSession
      .mockResolvedValueOnce({ admin_required: true, is_admin: true })
      .mockResolvedValueOnce({ admin_required: true, is_admin: false });
    mockLogoutAdminSession.mockResolvedValue();

    const { result } = renderHook(() => useAdminSession(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isAdmin).toBe(true));

    await act(async () => {
      await result.current.logout();
    });

    await waitFor(() => expect(result.current.isAdmin).toBe(false));
    expect(mockLogoutAdminSession).toHaveBeenCalledOnce();
  });
});