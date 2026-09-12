# CallMeMaybe frontend (Member D)

Desktop demo: upload a booking, approve a call plan, watch the live gate, take over only when a human decision is required.

## Run

Backend stub on `http://localhost:8000` first ([../README.md](../README.md)).

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000

## Routes

| URL | Screen |
|---|---|
| `/` | Upload + intent. Creates a session, then redirects to `/session/{id}` |
| `/session/{id}` | Upload + intent for that session |
| `/session/{id}/plan` | Plan card (approve / edit) |
| `/session/{id}/call` | Live call, gate verdicts, takeover |
| `/session/{id}/summary` | Outcome + attention metric |
| `/login` | Auth0 sign-in (`/auth/login`). Redirects home when `AUTH_DISABLED=true` |
| `/logout` | Auth0 sign-out |

Wrong-step URLs redirect to the step that matches session state. Unknown `session_id` redirects to `/`.

## Env

- `NEXT_PUBLIC_API_BASE` — C's FastAPI origin
- `NEXT_PUBLIC_FAKE_EVENTS` — `auto` (default) replays a canned call if no live events arrive after approve; `1` always; `0` never (live Twilio demo)
- `AUTH_DISABLED` — `true` skips Auth0. Set `false` and fill `AUTH0_*` + `APP_BASE_URL` to require sign-in

`GET /api/session/{id}/voice-token` is fetched on the plan screen (before approve) so the muted browser leg can join when A dials. `POST /api/session/{id}/takeover` unmutes the browser. Until Twilio is configured, the UI still runs (browser leg shows unavailable; takeover still starts the attention timer).
