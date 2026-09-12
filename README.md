# call-me-maybe

AI agent that makes the phone calls you've been putting off, and hands you the phone only when a human decision is required.

Shared API contract: [`docs/contract.md`](docs/contract.md).

## Backend (Member C)

Python 3.11, FastAPI. Session stubs return canned booking/plan data. Transcript turns run the two-tier policy gate (fail closed).

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run from `backend/` so `app` imports resolve. OpenAPI: http://localhost:8000/docs

Point `TIER1_*` at the IFM hosted API (see `.env.example`). Swap to self-hosted vLLM/llama.cpp by uncommenting the three lines under the IFM block. Without keys, the gate fail-closes to `ESCALATE`.

Local failure-test server:

```bash
cd backend
python -m app.llm.fake_server
pytest
```
