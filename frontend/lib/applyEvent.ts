import type {
  EventEnvelope,
  PolicyVerdict,
  Session,
  SessionState,
  Speaker,
  Summary,
  Turn,
} from "./types";

export function attachVerdict(turns: Turn[], verdict: PolicyVerdict): Turn[] {
  const next = [...turns];
  for (let i = next.length - 1; i >= 0; i -= 1) {
    if (next[i].speaker === "rep" && !next[i].verdict) {
      next[i] = { ...next[i], verdict };
      return next;
    }
  }
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
      const source =
        typeof event.data.source === "string" ? event.data.source : undefined;
      return {
        ...current,
        turns: [
          ...current.turns,
          { speaker, text, ts: event.ts, source },
        ],
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
  // Only real transcript turns cancel the demo tape. DIALING/IN_CALL from
  // Twilio must not hide the on-screen conversation during a live ring.
  return event.type === "transcript_turn";
}

export function turnsFromSession(session: Session): Turn[] {
  const rows = session.transcripts ?? [];
  const verdicts = session.verdicts ?? [];
  let vi = 0;
  const turns: Turn[] = [];
  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i];
    const speaker = asSpeaker(row.speaker);
    if (!speaker || typeof row.text !== "string" || !row.text) continue;
    const turn: Turn = {
      speaker,
      text: row.text,
      ts: i,
      source: typeof row.source === "string" ? row.source : undefined,
    };
    if (speaker === "rep" && vi < verdicts.length) {
      turn.verdict = verdicts[vi];
      vi += 1;
    }
    turns.push(turn);
  }
  return turns;
}
