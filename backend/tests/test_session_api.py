import httpx

from app.canned import CANNED_SUMMARY
from app.main import app
from app.models import SessionState
from app.store import set_state


async def _canned_summary(_session):
    return CANNED_SUMMARY


async def test_summary_409_before_call_ends(monkeypatch) -> None:
    monkeypatch.setattr("app.routers.session.generate_summary", _canned_summary)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = (await client.post("/api/session")).json()["session_id"]
        early = await client.get(f"/api/session/{session_id}/summary")
        assert early.status_code == 409
        set_state(session_id, SessionState.ENDED)
        ready = await client.get(f"/api/session/{session_id}/summary")
        assert ready.status_code == 200
        body = ready.json()
        assert "total_call_seconds" in body
        assert "human_attention_seconds" in body
