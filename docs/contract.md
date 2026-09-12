# CallMeMaybe — shared contract

Owner: Member C (backend + policy gate).

This document is frozen as of hour one. **Changes after T-10 require a Discord ping to all four members.** Teammates build against these paths, objects, and events — do not invent parallel shapes.

---

## 1. Session state machine

```
CREATED → EXTRACTED → PLAN_PENDING → PLAN_APPROVED → DIALING → IN_CALL → ESCALATING → HUMAN_CONTROL → ENDED → SUMMARIZED
```

| State | How we get here |
|---|---|
| `CREATED` | `POST /api/session` |
| `EXTRACTED` | `POST /api/session/{id}/document` succeeded |
| `PLAN_PENDING` | `POST /api/session/{id}/plan` returned a plan |
| `PLAN_APPROVED` | `POST /api/session/{id}/approve` |
| `DIALING` | A starts the Twilio/ElevenLabs dial |
| `IN_CALL` | A reports the call is live |
| `ESCALATING` | Gate returns `ESCALATE`, or B posts `/agent/tool/escalate` |
| `HUMAN_CONTROL` | User takes over in the browser |
| `ENDED` | Call ends (with or without escalation) |
| `SUMMARIZED` | Gemini summary + attention metric ready |

Legal skips: a call may go `IN_CALL → ENDED` without escalating. There is no path from `ESCALATE` back to agent turns.

---

## 2. Invariants

These are not prompt suggestions. They are control-flow rules.

1. **Fail closed.** Timeout, HTTP error, unparseable model output, missing config — the gate returns `ESCALATE` with `degraded: true`. A failure never returns `ALLOW`.
2. **Hard triggers are monotone.** The deterministic pre-check (currency symbols, fee/penalty/non-refundable language, payment-detail requests, identity verification) may only **force** `ESCALATE`. It may never return `ALLOW` or suppress a model escalation.
3. **Bounded action space, enforced in the orchestrator.** Once the gate returns `ESCALATE`, transition state and **permit no further agent turns**. The agent may only: identify itself, state the approved request, supply booking references, answer from the extracted document.
4. **Attention metric on `summary_ready`.** From A's timestamps: `total_call_seconds` and `human_attention_seconds` (leg C unmuted → call end). This is the number the demo closes on.

---

## 3. Objects

### `extracted`

```json
{
  "passenger_name": "string",
  "pnr": "string",
  "airline": "string",
  "flight_number": "string",
  "date": "string",
  "route": "string",
  "ticket_class": "string"
}
```

### `plan`

```json
{
  "goal": "string",
  "target_name": "string",
  "target_number": "string",
  "opening_script": "string",
  "permitted_actions": [],
  "escalation_triggers": [],
  "estimated_duration": "string"
}
```

### `policy_verdict`

```json
{
  "verdict": "ALLOW",
  "trigger": "none",
  "reason": "string",
  "confidence": 0.0,
  "tier": 1,
  "latency_ms": 0,
  "tier1_latency_ms": 0,
  "tier2_latency_ms": null,
  "provider_label": "K2-0.9B · IFM API",
  "degraded": false,
  "notes": []
}
```

| Field | Notes |
|---|---|
| `verdict` | `"ALLOW"` or `"ESCALATE"` |
| `trigger` | `"money"` \| `"authorization"` \| `"identity"` \| `"ambiguity"` \| `"none"` |
| `tier` | `0` = deterministic safety net, `1` = K2, `2` = Grok |
| `provider_label` | Comes from env. D renders this string as-is; swapping hosts relabels the UI with no frontend change. |
| `degraded` | `true` when we escalated because something broke (fail closed). |
| `tier2_latency_ms` | `null` when tier 2 was not invoked. |

### `summary`

```json
{
  "outcome": "string",
  "actions_taken": [],
  "open_items": [],
  "total_call_seconds": 0,
  "human_attention_seconds": 0
}
```

---

## 4. Event envelope

Every WebSocket message:

```json
{
  "type": "state_changed",
  "session_id": "abc",
  "ts": 1234567890,
  "data": {}
}
```

| `type` | `data` |
|---|---|
| `state_changed` | `{"state": "IN_CALL"}` (the new state) |
| `transcript_turn` | `{"speaker": "rep"\|"agent"\|"user", "text": "..."}` |
| `policy_verdict` | a `policy_verdict` object |
| `escalation` | `{"reason": "...", "verdict": {…}}` |
| `summary_ready` | a `summary` object |

`ts` is Unix epoch seconds (integer).

### `emit_event(session_id, type, data)`

C exposes this for A and B. They write **no** WebSocket code. Fan-out is C's job: persist (later) and push to every client subscribed on `WS /ws/session/{id}`.

---

## 5. HTTP / WebSocket endpoints (C owns)

Base URL is the backend origin (local: `http://localhost:8000`). All JSON request/response bodies unless noted.

### `POST /api/session`

Creates a session.

**Request:** empty object `{}` (optional body).

**Response `200`:**

```json
{"session_id": "abc"}
```

Initial state: `CREATED`. Emits `state_changed`.

### `POST /api/session/{id}/document`

Multipart upload of a booking. Field name: `file`.

**Response `200`:** an `extracted` object. State → `EXTRACTED`. Emits `state_changed`.

### `POST /api/session/{id}/plan`

Grok generates the call plan.

**Request:**

```json
{"goal": "cancel this flight"}
```

**Response `200`:** a `plan` object. State → `PLAN_PENDING`. Emits `state_changed`.

### `POST /api/session/{id}/approve`

User approved the plan. State → `PLAN_APPROVED`. Triggers A's `/dial` (A owns the dial implementation; C calls it).

**Request:** empty object `{}`.

**Response `200`:**

```json
{"session_id": "abc", "state": "PLAN_APPROVED"}
```

Emits `state_changed`.

### `GET /api/session/{id}`

Full session blob.

**Response `200`:**

```json
{
  "session_id": "abc",
  "state": "CREATED",
  "extracted": null,
  "plan": null,
  "summary": null,
  "verdicts": []
}
```

`extracted` / `plan` / `summary` are the objects above or `null` until set. `verdicts` is the policy audit trail for this session (empty until the gate runs).

### `GET /api/session/{id}/summary`

Gemini summary + attention metric.

**Response `200`:** a `summary` object. Available after state `SUMMARIZED` (hour-one stub returns canned zeros).

### `WS /ws/session/{id}`

Event stream for this session. Every message is the envelope in §4. On connect, C sends the current `state_changed` so D does not race.

### `POST /agent/transcript`

B posts turns. C runs the gate.

**Request:**

```json
{
  "session_id": "abc",
  "speaker": "rep",
  "text": "There is a $200 change fee."
}
```

**Response `200`:** a `policy_verdict` object. Emits `transcript_turn`, then `policy_verdict`. If `verdict` is `ESCALATE`, state → `ESCALATING`, emit `escalation`, and **no further agent turns**.

### `POST /agent/tool/escalate`

B's tool webhook (ElevenLabs agent decided to escalate, or A/B force it).

**Request:**

```json
{
  "session_id": "abc",
  "reason": "rep asked for payment details"
}
```

**Response `200`:** a `policy_verdict` with `verdict: "ESCALATE"`. State → `ESCALATING`. Emits `escalation`. Same no-further-agent-turns rule.

---

## 6. Errors

Unknown `session_id` → `404` with `{"detail": "session not found"}`.

Illegal state transition (e.g. approve before a plan exists) → `409` with `{"detail": "…"}`.

---

## 7. Repo conventions

- Own your directories. C owns `backend/` and this contract.
- Pull before push.
- Hour-one work lives on `member-c-backend-gate` until the team merges. Do not open a PR unless the team decides to.
- One use case, one session at a time, in-memory state with MongoDB write-through later.
- Out of scope: IVR/DTMF, parallel calling, multi-tenant concurrency, real airlines, retry/reconnection, rate limiting, production hardening.
