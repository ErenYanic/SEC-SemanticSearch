import { renderHook, act } from "@testing-library/react";
import { useEdgarSession } from "../useEdgarSession";

describe("useEdgarSession", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("starts unauthenticated when sessionStorage is empty", () => {
    const { result } = renderHook(() => useEdgarSession());
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.name).toBeNull();
    expect(result.current.email).toBeNull();
  });

  it("reads existing credentials from sessionStorage", () => {
    sessionStorage.setItem("edgar_name", "Jane Smith");
    sessionStorage.setItem("edgar_email", "jane@example.com");

    const { result } = renderHook(() => useEdgarSession());
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.name).toBe("Jane Smith");
    expect(result.current.email).toBe("jane@example.com");
  });

  it("login() stores credentials and updates state", () => {
    const { result } = renderHook(() => useEdgarSession());

    act(() => {
      result.current.login("John Doe", "john@example.com");
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.name).toBe("John Doe");
    expect(result.current.email).toBe("john@example.com");
    // Verify sessionStorage was written
    expect(sessionStorage.getItem("edgar_name")).toBe("John Doe");
    expect(sessionStorage.getItem("edgar_email")).toBe("john@example.com");
  });

  it("login() trims whitespace from credentials", () => {
    const { result } = renderHook(() => useEdgarSession());

    act(() => {
      result.current.login("  Jane Smith  ", "  jane@example.com  ");
    });

    expect(result.current.name).toBe("Jane Smith");
    expect(result.current.email).toBe("jane@example.com");
  });

  it("logout() clears credentials and updates state", () => {
    const { result } = renderHook(() => useEdgarSession());

    act(() => {
      result.current.login("John Doe", "john@example.com");
    });
    expect(result.current.isAuthenticated).toBe(true);

    act(() => {
      result.current.logout();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.name).toBeNull();
    expect(result.current.email).toBeNull();
    expect(sessionStorage.getItem("edgar_name")).toBeNull();
    expect(sessionStorage.getItem("edgar_email")).toBeNull();
  });

  it("isAuthenticated requires both name and email", () => {
    sessionStorage.setItem("edgar_name", "Jane Smith");
    // email missing

    const { result } = renderHook(() => useEdgarSession());
    expect(result.current.isAuthenticated).toBe(false);
  });
});
