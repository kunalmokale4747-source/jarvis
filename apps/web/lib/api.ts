export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const TOKEN_KEY = "jarvis_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  code: string;
  whatFailed: string;
  whatHappened: string;
  whatNext: string;
  status: number;

  constructor(
    status: number,
    payload: {
      code?: string;
      message?: string;
      what_failed?: string;
      what_happened?: string;
      what_next?: string;
    },
  ) {
    super(payload.message ?? `Request failed with status ${status}`);
    this.status = status;
    this.code = payload.code ?? "UNKNOWN";
    this.whatFailed = payload.what_failed ?? "Unknown";
    this.whatHappened = payload.what_happened ?? this.message;
    this.whatNext = payload.what_next ?? "Retry, and check API logs if it persists.";
  }
}

interface ApiOptions extends RequestInit {
  /** Skip the automatic redirect-to-login on 401 (used by the login page itself). */
  redirectOn401?: boolean;
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { redirectOn401 = true, headers, ...rest } = options;
  const token = getToken();

  const response = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(headers ?? {}),
    },
  });

  if (response.status === 401 && redirectOn401) {
    clearToken();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.assign("/login");
    }
    throw new ApiError(401, {
      code: "UNAUTHORIZED",
      message: "Your session ended.",
      what_failed: "Authentication",
      what_happened: "The session token is missing, expired, or revoked.",
      what_next: "Log in again.",
    });
  }

  const text = await response.text();
  const body = text ? JSON.parse(text) : {};

  if (!response.ok) {
    throw new ApiError(response.status, body);
  }
  return body as T;
}
