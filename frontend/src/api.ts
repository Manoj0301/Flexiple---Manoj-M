import type { SearchSpec, Session } from "./types";

export type RecruiterMark = {
  profile_id: string;
  verdict: "accept" | "reject";
  reason?: string;
};

export class ApiError extends Error {
  code: string;
  retryable: boolean;

  constructor(code: string, message: string, retryable: boolean) {
    super(message);
    this.code = code;
    this.retryable = retryable;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = data.error ?? {};
    throw new ApiError(
      error.code ?? "REQUEST_FAILED",
      error.message ?? "The request failed.",
      Boolean(error.retryable),
    );
  }
  return data as T;
}

function jsonHeaders(force?: string): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (force) headers["X-Force-Failure"] = force;
  return headers;
}

export function createSession(query: string, force?: string): Promise<Session> {
  return request("/api/search-sessions", {
    method: "POST",
    headers: jsonHeaders(force),
    body: JSON.stringify({ query }),
  });
}

export function editSpec(sessionId: string, spec: SearchSpec, force?: string): Promise<Session> {
  return request(`/api/search-sessions/${sessionId}/spec`, {
    method: "PATCH",
    headers: jsonHeaders(force),
    body: JSON.stringify(spec),
  });
}

export function refineSession(
  sessionId: string,
  message: string,
  feedback: RecruiterMark[],
  force?: string,
): Promise<Session> {
  return request(`/api/search-sessions/${sessionId}/refine`, {
    method: "POST",
    headers: jsonHeaders(force),
    body: JSON.stringify({ message, feedback }),
  });
}

export function freezeSession(sessionId: string): Promise<Session> {
  return request(`/api/search-sessions/${sessionId}/freeze`, { method: "POST" });
}

export function retrySession(sessionId: string): Promise<Session> {
  return request(`/api/search-sessions/${sessionId}/retry`, { method: "POST" });
}
