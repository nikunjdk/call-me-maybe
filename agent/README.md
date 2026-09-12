# Voice Agent (Member B)

ElevenLabs conversational agent: versioned prompts, tool schemas, and
config live here — not as dashboard-only state.

| Path | Purpose |
|---|---|
| `prompts/` | System prompt iterations (commit each change) |
| `config/` | Agent id, voice, turn-taking, tool schema as code |
| `PROGRESS.md` | Checklist for this workstream |

Runtime helpers that call C's `/agent/*` stubs live in
`backend/app/agent/`. Do not edit `backend/app/main.py` or
`backend/app/routers/agent.py`.

## Sync to ElevenLabs

```bash
# from repo root, with backend/.venv
backend/.venv/Scripts/python agent/sync_agent.py
```

When Vultr (or a tunnel) is up, set in `backend/.env` then re-sync:

```env
AGENT_WEBHOOK_BASE_URL=https://<public-backend-host>
```
