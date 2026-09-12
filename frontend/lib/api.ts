import { API_BASE } from "./env";
import type { Extracted, Plan, Session, SessionState, Summary } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json();
    if (
      body &&
      typeof body === "object" &&
      "detail" in body &&
      typeof (body as { detail: unknown }).detail === "string"
    ) {
      return (body as { detail: string }).detail;
    }
  } catch {
    // ignore
  }
  return res.statusText || `HTTP ${res.status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...init });
  if (!res.ok) {
    throw new ApiError(res.status, await readError(res));
  }
  return (await res.json()) as T;
}

export async function createSession(): Promise<string> {
  const data = await request<{ session_id: string }>("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  return data.session_id;
}

export async function uploadDocument(
  sessionId: string,
  file: File,
): Promise<Extracted> {
  const body = new FormData();
  body.append("file", file);
  return request<Extracted>(`/api/session/${sessionId}/document`, {
    method: "POST",
    body,
  });
}

export async function requestPlan(
  sessionId: string,
  goal: string,
): Promise<Plan> {
  return request<Plan>(`/api/session/${sessionId}/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ goal }),
  });
}

export async function approvePlan(
  sessionId: string,
): Promise<{ session_id: string; state: SessionState }> {
  return request(`/api/session/${sessionId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
}

export async function getSession(sessionId: string): Promise<Session> {
  return request<Session>(`/api/session/${sessionId}`);
}

export async function getSummary(sessionId: string): Promise<Summary> {
  return request<Summary>(`/api/session/${sessionId}/summary`);
}

export async function getVoiceToken(sessionId: string): Promise<string | null> {
  const res = await fetch(`${API_BASE}/api/session/${sessionId}/voice-token`);
  if (!res.ok) return null;
  const json: unknown = await res.json();
  if (!json || typeof json !== "object") return null;
  const record = json as Record<string, unknown>;
  if (typeof record.token === "string") return record.token;
  if (typeof record.accessToken === "string") return record.accessToken;
  return null;
}

export async function takeover(sessionId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/session/${sessionId}/takeover`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    return res.ok;
  } catch {
    return false;
  }
}
