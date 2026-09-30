import ky from "ky";
import { useSessionStore } from "../auth/session.store";

export interface ProblemDetail {
  type?: string;
  title: string;
  status: number;
  detail?: string;
  code?: string;
  errors?: Record<string, string[]> | Array<{ field?: string; message: string }>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | undefined;
  readonly title: string;
  readonly detail: string | undefined;
  readonly errors: Record<string, string[]> | Array<{ field?: string; message: string }> | undefined;
  readonly problem: ProblemDetail;

  constructor(problem: ProblemDetail) {
    super(problem.detail || problem.title || `API error ${problem.status}`);
    this.name = "ApiError";
    this.status = problem.status;
    this.code = problem.code;
    this.title = problem.title;
    this.detail = problem.detail;
    this.errors = problem.errors;
    this.problem = problem;
  }
}

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const response = await ky.post(`${API_ORIGIN}/api/v1/auth/refresh`, {
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "include",
        retry: 0,
      });

      const data = await response.json<{ accessToken: string; user?: any }>();
      const token = data.accessToken;
      if (token) {
        const currentUser = useSessionStore.getState().user;
        if (currentUser) {
          useSessionStore.getState().setSession(token, currentUser);
        }
        return token;
      }
      return null;
    } catch {
      useSessionStore.getState().clearSession();
      if (typeof window !== "undefined") {
        window.location.href = "/login?expired=1";
      }
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/**
 * Absolute same-origin base for the API. In the browser `window.location.origin`
 * makes this identical to the relative "/api/v1" (the Vite dev proxy and any
 * same-origin deployment behave the same), while in non-DOM runtimes (vitest,
 * SSR) the URL stays parseable instead of throwing "Failed to parse URL".
 */
const API_ORIGIN =
  typeof window !== "undefined" && window.location?.origin
    ? window.location.origin
    : "http://localhost";

export const api = ky.create({
  prefixUrl: `${API_ORIGIN}/api/v1`,
  retry: 0,
  hooks: {
    beforeRequest: [
      (request) => {
        const token = useSessionStore.getState().accessToken;
        if (token && !request.headers.has("Authorization")) {
          request.headers.set("Authorization", `Bearer ${token}`);
        }
      },
    ],
    afterResponse: [
      async (request, _options, response) => {
        if (response.status === 401) {
          const url = request.url;
          const isAuthPath =
            url.includes("auth/login") ||
            url.includes("auth/refresh") ||
            url.includes("auth/logout") ||
            url.includes("auth/invites");

          if (isAuthPath) {
            if (url.includes("auth/refresh")) {
              useSessionStore.getState().clearSession();
              if (typeof window !== "undefined") {
                window.location.href = "/login?expired=1";
              }
            }
          } else {
            const newToken = await refreshAccessToken();
            if (newToken) {
              const retryRequest = new Request(request, {
                headers: new Headers(request.headers),
              });
              retryRequest.headers.set("Authorization", `Bearer ${newToken}`);
              return ky(retryRequest);
            }

            useSessionStore.getState().clearSession();
            if (typeof window !== "undefined") {
              window.location.href = "/login?expired=1";
            }
          }
        }

        if (!response.ok) {
          let problem: ProblemDetail | null = null;
          try {
            const contentType = response.headers.get("content-type");
            if (
              contentType &&
              (contentType.includes("application/problem+json") ||
                contentType.includes("application/json"))
            ) {
              problem = await response.clone().json();
            }
          } catch {
            // Non-JSON error body fallback
          }

          if (problem) {
            throw new ApiError({
              status: problem.status || response.status,
              code: problem.code,
              title: problem.title || response.statusText,
              detail: problem.detail,
              errors: problem.errors,
              type: problem.type,
            });
          }

          throw new ApiError({
            status: response.status,
            title: response.statusText || "Request failed",
            detail: `HTTP error ${response.status}`,
          });
        }

        return response;
      },
    ],
  },
});
