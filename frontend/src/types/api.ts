/** The uniform error shape produced by `core.exceptions.api_exception_handler`. */
export interface ApiError {
  detail: string;
  code: string;
  errors: Record<string, string[]> | null;
}

/** The envelope produced by `core.pagination.DefaultPagination`. */
export interface Paginated<T> {
  results: T[];
  pagination: {
    count: number;
    page: number;
    pages: number;
    page_size: number;
    next: string | null;
    previous: string | null;
  };
}

export interface HealthStatus {
  status: "ok" | "error";
  database: "ok" | "error";
  version: string;
}
