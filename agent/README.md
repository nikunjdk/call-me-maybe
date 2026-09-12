# Voice Agent (Member B)

ElevenLabs conversational agent: versioned prompts, tool schemas, and
config live here — not as dashboard-only state.

| Path | Purpose |
|---|---|
| `prompts/` | System prompt iterations (commit each change) |
| `config/` | Agent id, voice, turn-taking, tool schema as code |
| `PROGRESS.md` | Checklist for this workstream |

Runtime helpers that call C's `/agent/*` routes live in
`backend/app/agent/`. Telephony join is `POST /twilio/voice/agent`
(ElevenLabs `register_call`). Transcript ingress for the live gate is
`POST /agent/elevenlabs/event` (plus contract `POST /agent/transcript`).

## Sync to ElevenLabs

```bash
# from repo root, with backend/.venv
backend/.venv/Scripts/python agent/sync_agent.py
```

When a tunnel is up, set in `backend/.env` then re-run:

```env
PUBLIC_BASE_URL=https://<public-backend-host>
AGENT_WEBHOOK_BASE_URL=https://<public-backend-host>
```

`sync_agent.py` also patches TTS/ASR to `ulaw_8000` (required for Twilio `register_call`).

Point the ElevenLabs Agents conversation / post-call webhook at
`{AGENT_WEBHOOK_BASE_URL}/agent/elevenlabs/event` so turns hit C's gate.

Live Twilio audio is also transcribed by **Scribe v2 Realtime**: the rep TwiML
starts a Media Stream to `wss://<PUBLIC_BASE_URL>/twilio/media/{session_id}`.
Committed utterances run the policy gate the same as `/agent/transcript`.
