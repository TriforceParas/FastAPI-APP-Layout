/**
 * Typed fetch wrapper for the FastAPI backend.
 *
 *   const users = await api.get<UsersPage>("/users", { q: "ada" });
 *   await api.post("/users", { name, email, password });
 *
 * - Always same-origin (`/api/...`), cookies included automatically.
 * - Sends the CSRF token on every state-changing request and retries once
 *   if the server reports `csrf_failed` (for example after a token rotation).
 * - Throws `ApiError` with a human-readable `message` on non-2xx.
 */

export type Query = Record<string, string | number | boolean | null | undefined>;

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;
  /** X-Request-ID of the failed request: quote it to support to find it in the server logs. */
  readonly requestId: string | null;
  constructor(status: number, detail: unknown, message: string, requestId: string | null = null) {
    super(message);
    this.status = status;
    this.detail = detail;
    this.requestId = requestId;
  }
}

let csrfToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

/** Called on any 401 so the auth layer can show the login screen. */
export function onUnauthorized(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string") {
    const known: Record<string, string> = {
      csrf_failed: "Your session token expired. Please try again.",
      password_change_required: "You must change your password first.",
    };
    return known[detail] ?? detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item: { loc?: string[]; msg?: string }) => {
        const field = item.loc?.filter((part) => part !== "body").join(".");
        return field ? `${field}: ${item.msg}` : item.msg;
      })
      .join("; ");
  }
  if (status === 429) return "Too many requests. Please wait a moment.";
  if (status >= 500) return "The server had a problem. Please try again.";
  return `Request failed (${status}).`;
}

async function refreshCsrf() {
  const res = await fetch("/api/auth/status", {
    credentials: "same-origin",
    cache: "no-store",
  });
  const data = (await res.json().catch(() => null)) as { csrf_token?: string } | null;
  if (data?.csrf_token) csrfToken = data.csrf_token;
}

async function request<T>(
  method: string,
  path: string,
  { body, query }: { body?: unknown; query?: Query } = {},
  retried = false,
): Promise<T> {
  const url = new URL(`/api${path}`, window.location.origin);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }

  const unsafe = method !== "GET" && method !== "HEAD";
  if (unsafe && !csrfToken) await refreshCsrf();

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (unsafe && csrfToken) headers["X-CSRF-Token"] = csrfToken;

  const res = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
    cache: "no-store",
  });

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data: unknown = res.status === 204 || !isJson ? undefined : await res.json();

  if (!res.ok) {
    const detail = (data as { detail?: unknown } | undefined)?.detail;
    if (res.status === 403 && detail === "csrf_failed" && !retried) {
      await refreshCsrf();
      return request<T>(method, path, { body, query }, true);
    }
    if (res.status === 401 && !path.startsWith("/auth/")) unauthorizedHandler?.();
    const requestId = res.headers.get("x-request-id");
    let text = errorMessage(detail, res.status);
    // Server-side failures: show a reference so the user can quote it to support.
    if (res.status >= 500 && requestId) text = `${errorMessage(undefined, res.status)} Reference: ${requestId}`;
    throw new ApiError(res.status, detail, text, requestId);
  }

  const token = (data as { csrf_token?: unknown } | undefined)?.csrf_token;
  if (typeof token === "string") csrfToken = token;
  return data as T;
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>("GET", path, { query }),
  post: <T = void>(path: string, body?: unknown) => request<T>("POST", path, { body }),
  put: <T = void>(path: string, body?: unknown) => request<T>("PUT", path, { body }),
  patch: <T = void>(path: string, body?: unknown) => request<T>("PATCH", path, { body }),
  delete: <T = void>(path: string) => request<T>("DELETE", path),
};
