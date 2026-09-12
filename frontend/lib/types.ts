export type SessionState =
  | "CREATED"
  | "EXTRACTED"
  | "PLAN_PENDING"
  | "PLAN_APPROVED"
  | "DIALING"
  | "IN_CALL"
  | "ESCALATING"
  | "HUMAN_CONTROL"
  | "ENDED"
  | "SUMMARIZED";

export type Trigger = "money" | "authorization" | "identity" | "ambiguity" | "none";
export type Verdict = "ALLOW" | "ESCALATE";
export type Speaker = "rep" | "agent" | "user";
export type EventType =
  | "state_changed"
  | "transcript_turn"
  | "policy_verdict"
  | "escalation"
  | "summary_ready";

export type Extracted = {
  passenger_name: string;
  pnr: string;
  airline: string;
  flight_number: string;
  date: string;
  route: string;
  ticket_class: string;
};

export type Plan = {
  goal: string;
  target_name: string;
  target_number: string;
  opening_script: string;
  permitted_actions: string[];
  escalation_triggers: string[];
  estimated_duration: string;
};

export type PolicyVerdict = {
  verdict: Verdict;
  trigger: Trigger;
  reason: string;
  confidence: number;
  tier: 0 | 1 | 2;
  latency_ms: number;
  tier1_latency_ms: number;
  tier2_latency_ms: number | null;
  provider_label: string;
  degraded: boolean;
  notes: string[];
};

export type Summary = {
  outcome: string;
  actions_taken: string[];
  open_items: string[];
  total_call_seconds: number;
  human_attention_seconds: number;
};

export type Session = {
  session_id: string;
  state: SessionState;
  extracted: Extracted | null;
  plan: Plan | null;
  summary: Summary | null;
  verdicts: PolicyVerdict[];
};

export type EventEnvelope = {
  type: EventType;
  session_id: string;
  ts: number;
  data: Record<string, unknown>;
};

export type Turn = {
  speaker: Speaker;
  text: string;
  ts: number;
  verdict?: PolicyVerdict;
};

export type VoiceStatus = "off" | "muted" | "live" | "unavailable";
