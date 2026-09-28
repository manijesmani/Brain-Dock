import type { ApiError } from "@/types/api";

/** The API's error body, when the failure came from the API at all. */
function apiError(error: unknown): Partial<ApiError> | undefined {
  return (error as { response?: { data?: Partial<ApiError> } } | null)?.response?.data;
}

export function errorStatus(error: unknown): number | undefined {
  return (error as { response?: { status?: number } } | null)?.response?.status;
}

export function errorCode(error: unknown): string | undefined {
  return apiError(error)?.code;
}

/** No answer came back at all: the connection failed, not the request. */
function isNetworkError(error: unknown): boolean {
  const failure = error as { request?: unknown; response?: unknown } | null;
  return Boolean(failure?.request) && !failure?.response;
}

/** The server's own sentence for what went wrong, or `fallback` without one. */
export function errorMessage(error: unknown, fallback: string): string {
  // Nginx turns an oversized body away before Django sees it, with a page
  // of its own rather than the API's JSON.
  if (errorStatus(error) === 413) return "حجم فایل بیشتر از حد مجاز است.";
  if (isNetworkError(error)) {
    return "ارتباط با سرور برقرار نشد. اتصال اینترنت را بررسی کن و دوباره امتحان کن.";
  }

  const detail = apiError(error)?.detail;
  return typeof detail === "string" && detail ? detail : fallback;
}
