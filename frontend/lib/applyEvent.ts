import type {
  EventEnvelope,
  PolicyVerdict,
  SessionState,
  Speaker,
  Summary,
  Turn,
} from "./types";

export function attachVerdict(turns: Turn[], verdict: PolicyVerdict): Turn[] {
  const next = [...turns];
  for (let i = next.length - 1; i >= 0; i -= 1) {
    if (!next[i].verdict) {
      next[i] = { ...next[i], verdict };
      return next;
    }
  }
  return next;
}

function asState(value: unknown): SessionState | null {
  if (typeof value !== "string") return null;
  return value as SessionState;
}

function asSpeaker(value: unknown): Speaker | null {
  if (value === "rep" || value === "agent" || value === "user") return value;
  return null;
}

export function applyEvent<T extends { state: SessionState | null; turns: Turn[]; summary: Summary | null; escalationReason: string | null }>(
  current: T,
  event: EventEnvelope,
): T {
  switch (event.type) {
    case "state_changed": {
      const state = asState(event.data.state);
      if (!state) return current;
      return { ...current, state };
    }
    case "transcript_turn": {
      const speaker = asSpeaker(event.data.speaker);
      const text = event.data.text;
      if (!speaker || typeof text !== "string") return current;
      return {
        ...current,
        turns: [...current.turns, { speaker, text, ts: event.ts }],
      };
    }
    case "policy_verdict": {
      return {
        ...current,
        turns: attachVerdict(current.turns, event.data as unknown as PolicyVerdict),
      };
    }
    case "escalation": {
      const verdict = event.data.verdict as PolicyVerdict | undefined;
      return {
        ...current,
        state: "ESCALATING",
        escalationReason:
          typeof event.data.reason === "string" ? event.data.reason : current.escalationReason,
        turns: verdict ? attachVerdict(current.turns, verdict) : current.turns,
      };
    }
    case "summary_ready": {
      return {
        ...current,
        state: "SUMMARIZED",
        summary: event.data as unknown as Summary,
      };
    }
    default:
      return current;
  }
}

export function isLiveCallSignal(event: EventEnvelope): boolean {
  if (event.type === "transcript_turn") return true;
  if (event.type !== "state_changed") return false;
  const state = asState(event.data.state);
  return state === "DIALING" || state === "IN_CALL";
}
