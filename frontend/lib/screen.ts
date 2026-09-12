import type { SessionState, Summary } from "./types";

export function isStubSummary(summary: Summary | null): boolean {
  if (!summary) return true;
  return summary.outcome.toLowerCase().startsWith("stub");
}

export function screenFor(
  state: SessionState | null,
  summary: Summary | null,
): 1 | 2 | 3 | 4 {
  if (state === "SUMMARIZED" || (summary && !isStubSummary(summary))) return 4;
  if (!state || state === "CREATED" || state === "EXTRACTED") return 1;
  if (state === "PLAN_PENDING") return 2;
  return 3;
}
