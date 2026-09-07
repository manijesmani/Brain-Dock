import axios from "axios";

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

const UNSAFE_METHODS = new Set(["post", "put", "patch", "delete"]);

apiClient.interceptors.request.use((config) => {
  const method = config.method?.toLowerCase();

  if (method && UNSAFE_METHODS.has(method)) {
    const csrfToken = readCookie("csrftoken");
    if (csrfToken) {
      config.headers.set("X-CSRFToken", csrfToken);
    }
  }

  return config;
});
