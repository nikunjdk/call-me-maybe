# Live demo runbook

Production origin: **https://207.148.20.54.sslip.io**

Seeded start (Alex Chen / UA 482 cancel, `PLAN_PENDING`):  
https://207.148.20.54.sslip.io/session/demo-alex-chen/plan

API restart reseeds that session. Mongo write-through hydrates other sessions on boot.

## Preflight

1. Frontend production must keep `NEXT_PUBLIC_FAKE_EVENTS=0` so the canned tape cannot overlay a live call.
2. Backend `.env` on the box:
   - `PUBLIC_BASE_URL=https://207.148.20.54.sslip.io`
   - `AGENT_WEBHOOK_BASE_URL=https://207.148.20.54.sslip.io`
3. After any URL change, from repo root on the server:  
   `/opt/callmemaybe/backend/.venv/bin/python /opt/callmemaybe/agent/sync_agent.py`
4. Twilio Voice URLs (all POST, HTTPS):

| Number / app | Path |
|---|---|
| Agent PSTN (`TWILIO_AGENT_NUMBER`) | `/twilio/voice/agent` |
| Browser TwiML app | `/twilio/voice/browser` |
| Scripted sim-rep | `/twilio/voice/rep` |
| Status / conference callback | `/twilio/status` |

5. ElevenLabs:

| Webhook | Path |
|---|---|
| Escalate tool | `/agent/tool/escalate` |
| Conversation / post-call | `/agent/elevenlabs/event` |
| Contract turns | `/agent/transcript` |
| Twilio Media Stream (Scribe) | `wss://…/twilio/media/{session_id}` |

6. Atlas Network Access must allow `207.148.20.54`. Health: https://207.148.20.54.sslip.io/health
7. Leg B requires `TWILIO_AGENT_NUMBER` whose Voice URL is `/twilio/voice/agent`. After prompt or audio-format changes, re-run `sync_agent.py` (patches `ulaw_8000`).
8. Architecture slide: [`docs/architecture.html`](architecture.html)

## On stage (3 minutes)

1. Open the seeded plan URL. Confirm booking + opening script. Click **Approve**.
2. Call connects. Agent identifies as AI and states the cancel request only.
3. Rep hits a fee / payment / identity line. Gate returns **ESCALATE** (hard net or K2). Agent stalls. No further agent turns (HTTP 409).
4. Click **Take over**. You are live; rep is already briefed.
5. Hang up. Summary shows `total_call_seconds` and **`human_attention_seconds`** (unmuted → end). That number is the pitch.

Backup if Twilio is down: local frontend with `NEXT_PUBLIC_FAKE_EVENTS=auto` still replays the canned tape.

## Freeze notes

Phase 2 (self-host K2 on a Vultr GPU) was not shipped. Live tier-1 is hosted IFM `K2-Horizon-375B-A23B`. Eval table is in `policy/bench_results.md`.
