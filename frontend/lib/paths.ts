import { isStubSummary } from "./screen";
import type { SessionState, Summary } from "./types";

export type SessionStep = "intent" | "plan" | "call" | "summary";

export const routes = {
  home: "/",
  login: "/login",
  logout: "/logout",
  authLogin: "/auth/login",
  authLogout: "/auth/logout",
  session: (id: string) => `/session/${id}`,
  plan: (id: string) => `/session/${id}/plan`,
  call: (id: string) => `/session/${id}/call`,
  summary: (id: string) => `/session/${id}/summary`,
  step(id: string, step: SessionStep): string {
    if (step === "plan") return routes.plan(id);
    if (step === "call") return routes.call(id);
    if (step === "summary") return routes.summary(id);
    return routes.session(id);
  },
};

export function pathFor(
  sessionId: string | null,
  state: SessionState | null,
  summary: Summary | null,
): string {
  if (!sessionId || !state || state === "CREATED" || state === "EXTRACTED") {
    return sessionId ? routes.session(sessionId) : routes.home;
  }
  if (state === "PLAN_PENDING") return routes.plan(sessionId);
  if (state === "SUMMARIZED" || (summary && !isStubSummary(summary))) {
    return routes.summary(sessionId);
  }
  return routes.call(sessionId);
}
