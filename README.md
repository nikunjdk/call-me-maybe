# call-me-maybe

AI agent that makes the phone calls you've been putting off, and hands you the phone only when a human decision is required.

**Production (Vultr + TLS):** https://207.148.20.54.sslip.io

Shared API contract: [`docs/contract.md`](docs/contract.md). Live demo runbook: [`docs/demo-script.md`](docs/demo-script.md). Architecture slide: [`docs/architecture.html`](docs/architecture.html).

**Gate (eval, n=40):** accuracy **0.975**, **0 false allows**, 1 false escalate, tier-2 rate **0.00**, p50 **267ms**, p95 **1758ms**. Live model `IFM/K2-Horizon-375B-A23B`. Numbers from [`policy/bench_results.md`](policy/bench_results.md) — do not quote others.

## Backend (Member C)

Python 3.11, FastAPI. Transcript turns run the two-tier policy gate (fail closed). Booking extract / plan / summary go through the provider module (Gemini + Grok) and fall back to canned data if those keys are missing. Optional MongoDB Atlas write-through.

**Live tier-1 model:** `IFM/K2-Horizon-375B-A23B` (only hosted K2 size that classified). Measured on 40 labelled turns: accuracy 0.975, **0 false allows**, 1 false escalate, p50 267ms, p95 1758ms. See [`policy/bench_results.md`](policy/bench_results.md).

```bash
cd backend
./start.sh
```

`start.sh` creates `.venv` if needed. Put API keys in `backend/.env.local` — that file is not overwritten when the README `cp .env.example .env` command runs.

Run from `backend/` so `app` imports resolve. OpenAPI: http://localhost:8000/docs

A-facing extras (timestamps + call-leg state), still HTTP so A writes no WebSocket code:

- `POST /api/session/{id}/state` `{"state":"DIALING"|"IN_CALL"|"HUMAN_CONTROL"|"ENDED"}`
- `POST /api/session/{id}/timestamps` `{"call_started_ts","human_unmuted_ts","call_ended_ts"}`

```bash
cd backend
python -m app.llm.fake_server
pytest
python -m app.policy.bench --compare
```

## Frontend

Next.js 15 four-screen demo (upload → plan → call → summary) against the local backend. Leave Auth0 off (`AUTH_DISABLED=true`).

**Live vs fake**

- **Fake (default locally):** Without Twilio credentials, approve still advances and `NEXT_PUBLIC_FAKE_EVENTS=auto` replays a canned call after approve.
- **Live / Vultr:** `PUBLIC_BASE_URL` and `AGENT_WEBHOOK_BASE_URL` are `https://207.148.20.54.sslip.io`. Production frontend uses `NEXT_PUBLIC_FAKE_EVENTS=0`. Follow [`docs/demo-script.md`](docs/demo-script.md).

Seeded demo start (plan, waiting on Approve): https://207.148.20.54.sslip.io/session/demo-alex-chen/plan

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open http://localhost:3000. `.env` should keep `NEXT_PUBLIC_API_BASE=http://localhost:8000`, `AUTH_DISABLED=true`. Use `NEXT_PUBLIC_FAKE_EVENTS=auto` without Twilio; use `0` for the live conference path.
