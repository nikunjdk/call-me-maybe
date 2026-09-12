import type { EventEnvelope, EventType, PolicyVerdict } from "./types";

type TapeStep =
  | { wait: number; type: EventType; data: Record<string, unknown> }
  | { waitFor: "takeover" };

const ALLOW: PolicyVerdict = {
  verdict: "ALLOW",
  trigger: "none",
  reason: "Routine booking lookup — within permitted actions.",
  confidence: 0.97,
  tier: 1,
  latency_ms: 61,
  tier1_latency_ms: 61,
  tier2_latency_ms: null,
  provider_label: "K2",
  degraded: false,
  notes: [],
};

const ESCALATE: PolicyVerdict = {
  verdict: "ESCALATE",
  trigger: "money",
  reason: "Rep introduced a change fee.",
  confidence: 0.99,
  tier: 1,
  latency_ms: 58,
  tier1_latency_ms: 58,
  tier2_latency_ms: null,
  provider_label: "K2",
  degraded: false,
  notes: [],
};

const TAPE: TapeStep[] = [
  { wait: 400, type: "state_changed", data: { state: "DIALING" } },
  { wait: 900, type: "state_changed", data: { state: "IN_CALL" } },
  {
    wait: 700,
    type: "transcript_turn",
    data: {
      speaker: "agent",
      text: "Hello, this is an AI assistant calling on behalf of Alex Chen. I have their booking reference ABC123 for United flight UA 482 on September 18 from San Francisco to New York. They would like to cancel this reservation.",
    },
  },
  { wait: 350, type: "policy_verdict", data: { ...ALLOW, latency_ms: 54, tier1_latency_ms: 54 } },
  {
    wait: 1100,
    type: "transcript_turn",
    data: {
      speaker: "rep",
      text: "I have that reservation. How can I help you today?",
    },
  },
  { wait: 350, type: "policy_verdict", data: { ...ALLOW } },
  {
    wait: 1400,
    type: "transcript_turn",
    data: {
      speaker: "agent",
      text: "They would like to cancel this reservation and request a refund to the original form of payment.",
    },
  },
  { wait: 350, type: "policy_verdict", data: { ...ALLOW, latency_ms: 59, tier1_latency_ms: 59 } },
  {
    wait: 1800,
    type: "transcript_turn",
    data: {
      speaker: "rep",
      text: "I can cancel that. There's a $150 change fee to process this.",
    },
  },
  { wait: 350, type: "policy_verdict", data: { ...ESCALATE } },
  {
    wait: 200,
    type: "escalation",
    data: { reason: "Rep introduced a $150 change fee.", verdict: ESCALATE },
  },
  { waitFor: "takeover" },
  {
    wait: 1600,
    type: "transcript_turn",
    data: {
      speaker: "user",
      text: "I'll cover the fee question. Can you waive it given this was a schedule change?",
    },
  },
  {
    wait: 1800,
    type: "transcript_turn",
    data: {
      speaker: "rep",
      text: "I can waive the $150 fee this once and cancel the reservation. You'll see the refund in five to seven days.",
    },
  },
  { wait: 800, type: "state_changed", data: { state: "ENDED" } },
  {
    wait: 700,
    type: "summary_ready",
    data: {
      outcome: "Flight UA 482 cancelled. $150 fee waived. Refund to original payment in 5–7 days.",
      actions_taken: [
        "Identified as AI acting for Alex Chen",
        "Stated cancel request for PNR ABC123",
        "Handed off at the fee decision",
        "Fee waived; reservation cancelled",
      ],
      open_items: ["Watch for refund confirmation email"],
      total_call_seconds: 252,
      human_attention_seconds: 38,
    },
  },
];

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(resolve, ms);
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(new DOMException("aborted", "AbortError"));
    };
    if (signal.aborted) {
      onAbort();
      return;
    }
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

export async function runFakeReplay(opts: {
  sessionId: string;
  emit: (event: EventEnvelope) => void;
  signal: AbortSignal;
  waitForTakeover: () => Promise<void>;
}): Promise<void> {
  try {
    for (const step of TAPE) {
      if (opts.signal.aborted) return;
      if ("waitFor" in step) {
        await opts.waitForTakeover();
        continue;
      }
      await sleep(step.wait, opts.signal);
      if (opts.signal.aborted) return;
      opts.emit({
        type: step.type,
        session_id: opts.sessionId,
        ts: Math.floor(Date.now() / 1000),
        data: step.data,
      });
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    throw error;
  }
}
