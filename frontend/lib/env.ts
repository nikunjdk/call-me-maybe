export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export const STORAGE_KEY = "cmm-session-id";

export function fakeEventsMode(): "off" | "on" | "auto" {
  const value = process.env.NEXT_PUBLIC_FAKE_EVENTS;
  if (value === "0" || value === "false") return "off";
  if (value === "1" || value === "true") return "on";
  return "auto";
}

export function wsUrl(sessionId: string): string {
  const base = API_BASE.replace(/^http/i, "ws");
  return `${base}/ws/session/${sessionId}`;
}
