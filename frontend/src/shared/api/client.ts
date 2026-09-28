import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

import { errorCode } from "@/shared/api/errors";
import { readCookie } from "@/shared/lib/cookies";

/**
 * The single axios instance every request goes through.
 *
 * Authentication is session-cookie based, so `withCredentials` is mandatory
 * and Django's CSRF token has to travel on every unsafe method.
 */
export const apiClient = axios.create({
  baseURL: "/api",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

/**
 * The project's own name for the CSRF cookie, CSRF_COOKIE_NAME in
 * config.settings.base. A plain `csrftoken` set for the parent domain by a
 * neighbouring site would otherwise be read here in place of this one.
 */
const CSRF_COOKIE = "braindock_csrftoken";

const UNSAFE_METHODS = new Set(["post", "put", "patch", "delete"]);

apiClient.interceptors.request.use((config) => {
  const method = config.method?.toLowerCase();

  if (method && UNSAFE_METHODS.has(method)) {
    const csrfToken = readCookie(CSRF_COOKIE);
    if (csrfToken) {
      config.headers.set("X-CSRFToken", csrfToken);
    }
  }

  return config;
});

/** Requests already sent again once after a CSRF refusal. */
const retried = new WeakSet<InternalAxiosRequestConfig>();

// A write refused for its CSRF token -- the cookie gone, or stale -- was
// never carried out, so it is safe to send again. A fresh cookie is fetched
// first and the request goes out once more, instead of every write failing
// until the person thinks to sign out and in again.
apiClient.interceptors.response.use(undefined, async (error: AxiosError) => {
  const config = error.config;
  if (config && errorCode(error) === "csrf_failed" && !retried.has(config)) {
    retried.add(config);
    await apiClient.get("/auth/csrf/");
    return apiClient.request(config);
  }
  throw error;
});
