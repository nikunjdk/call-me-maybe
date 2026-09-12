# PROGRESS — Voice Agent (B)

Update this file yourself as work happens. This is what a fresh Cursor
session reads to know exactly where things stand — it replaces re-pasting
old conversation history.

Format per item: `- [ ]` unchecked, `- [x]` done. One line of note directly
underneath once done. Nothing else goes in this file — no diary, no plans
that haven't started.

## Checklist

- [x] Scaffold `/agent` and `/backend/app/agent/` package layout (README stub, empty modules C can import against)
  - Added agent/{README,prompts,config} and backend/app/agent/{__init__,client,settings}. Manual test: `cd backend && python -c "from app.agent import post_transcript, post_escalate"`.
- [x] Create ElevenLabs conversational agent; put API key in shared `.env` (never commit secrets); note agent_id in `/agent` config
  - Created agent_2201m2ac4zx4fbfr7gchwckrtyw5 (Matilda voice); id in agent/config/agent.json + backend/.env. Manual test: ElevenLabs dashboard shows the agent / SDK create returned agent_id.
- [x] Draft system prompt as versioned file in `/agent` — mandatory AI disclosure, four permitted actions only, stall phrase (~10–15s), explicit escalation triggers
  - `agent/prompts/system_v1.md` synced to live agent via `agent/sync_agent.py`.
- [x] Agent config as code in `/agent` — voice, tool schemas (`escalate`), turn-taking; commit each prompt iteration
  - `agent/config/agent.json` + `config/tools/escalate.json`; tool_id tool_8001m2acejwmfnbats6h64jnfx82.
- [x] Wire escalate tool webhook to `POST /agent/tool/escalate` with contract body `{session_id, reason}`; stall on fire
  - Webhook on tool → localhost:8000; `escalate_now` returns ESCALATE + stall. Test: live POST escalate against C stubs.
- [x] Widget soak: playing rep, escalation fires reliably on fee line e.g. "there's a $150 change fee"
  - `agent/sim_fee.py` simulate-conversation: status 200, escalate_signal True on $150 fee line.
- [x] Per-turn transcript emission: after every completed turn `POST /agent/transcript`; handle `ALLOW` vs `ESCALATE` inside the turn loop before speaking again
  - `backend/app/agent/turn_loop.py` `on_turn_complete`. Test: session + turn → ALLOW; escalate_now → block.
- [ ] T-6 integration checkpoint with A — agent joins Twilio conference; set telephony audio to 8kHz μ-law explicitly; go/no-go called out
  - Code path: POST /twilio/voice/agent via register_call + add_agent_leg from dial(); needs live Twilio/EL keys + PUBLIC_BASE_URL.
- [ ] Escalation end-to-end: fee line → gate/tool escalate → stall → C signals browser; tune stall so it does not clip
- [x] Latency pass: trim prompt/preamble/turn detection; target under ~1.2s per turn; minimize pre-escalation turn count
  - `prompts/system_v2.md`, shorter first_message, turn_timeout 5; synced. Re-measure on live call with A.
- [ ] Freeze prompt; five clean end-to-end runs recorded
- [x] Fallback ready: ElevenLabs `transfer_to_number` warm-transfer if conference path fails at T-6
  - Schema at `agent/config/tools/transfer_to_number.json` (not attached until T-6 fails).

## Log
- Scaffold: agent/ + backend/app/agent/ importable stubs; test `from app.agent import post_transcript, post_escalate`.
- ElevenLabs agent created (agent_2201m2ac4zx4fbfr7gchwckrtyw5); config + .env updated.
- Prompt v1 + escalate tool synced; turn_loop + client wired; transfer_to_number fallback schema ready.
- Latency: system_v2 synced; AGENT_WEBHOOK_BASE_URL deferred until Vultr — re-run sync_agent.py then.
- Widget soak via sim_fee.py (fee → escalate signal). settings.py reads agent_id from config fallback.
- Live demo path: register_call agent leg + /agent/elevenlabs/event + escalate session_id dynamic_variable; awaiting user Twilio/EL secrets + tunnel.
