import { AxiosError, type AxiosResponse } from "axios";
import { extractApiError } from "../api";

describe("extractApiError", () => {
  it("extracts backend ErrorResponse shape", () => {
    const axiosErr = new AxiosError("Bad Request", "ERR_BAD_REQUEST", undefined, undefined, {
      data: { error: "NotFoundError", message: "Filing not found", details: "abc" },
      status: 404,
      statusText: "Not Found",
      headers: {},
      config: {} as never,
    } as AxiosResponse);

    const result = extractApiError(axiosErr);
    expect(result.error).toBe("NotFoundError");
    expect(result.message).toBe("Filing not found");
    expect(result.details).toBe("abc");
  });

  it("extracts FastAPI 422 validation errors (array detail)", () => {
    const axiosErr = new AxiosError("Unprocessable", "ERR_BAD_REQUEST", undefined, undefined, {
      data: {
        detail: [
          { loc: ["body", "query"], msg: "field required", type: "value_error.missing" },
          { loc: ["body", "top_k"], msg: "must be positive", type: "value_error" },
        ],
      },
      status: 422,
      statusText: "Unprocessable Entity",
      headers: {},
      config: {} as never,
    } as AxiosResponse);

    const result = extractApiError(axiosErr);
    expect(result.error).toBe("ValidationError");
    expect(result.message).toBe("field required; must be positive");
  });

  it("extracts FastAPI 422 validation errors (string detail)", () => {
    const axiosErr = new AxiosError("Unprocessable", "ERR_BAD_REQUEST", undefined, undefined, {
      data: { detail: "Not authenticated" },
      status: 401,
      statusText: "Unauthorized",
      headers: {},
      config: {} as never,
    } as AxiosResponse);

    const result = extractApiError(axiosErr);
    expect(result.error).toBe("ValidationError");
    expect(result.message).toBe("Not authenticated");
  });

  it("handles network error (no response)", () => {
    const err = new Error("Network Error");

    const result = extractApiError(err);
    expect(result.error).toBe("NetworkError");
    expect(result.message).toBe("Network Error");
  });

  it("handles non-Error unknown values", () => {
    const result = extractApiError("something weird");
    expect(result.error).toBe("NetworkError");
    expect(result.message).toBe("An unexpected error occurred");
  });

  it("handles AxiosError with no response data", () => {
    const axiosErr = new AxiosError("timeout", "ECONNABORTED");

    const result = extractApiError(axiosErr);
    expect(result.error).toBe("NetworkError");
    expect(result.message).toBe("timeout");
  });
});