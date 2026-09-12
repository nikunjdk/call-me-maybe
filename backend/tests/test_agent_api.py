import httpx

from app.main import app
from tests.conftest import set_mode


async def test_transcript_fail_closed_then_blocks_agent_turns(fake_llm) -> None:
    set_mode(fake_llm["origin"], "prose")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = (await client.post("/api/session")).json()["session_id"]
        first = await client.post(
            "/agent/transcript",
            json={"session_id": session_id, "speaker": "rep", "text": "How can I help?"},
        )
        assert first.status_code == 200
        body = first.json()
        assert body["verdict"] == "ESCALATE"
        assert body["degraded"] is True
        second = await client.post(
            "/agent/transcript",
            json={"session_id": session_id, "speaker": "agent", "text": "continuing"},
        )
        assert second.status_code == 409
        third = await client.post(
            "/agent/tool/escalate",
            json={"session_id": session_id, "reason": "already escalating"},
        )
        assert third.status_code == 409
