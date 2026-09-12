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
            json={"session_id": session_id, "speaker": "agent", "text": "One moment please"},
        )
        assert second.status_code == 200
        third = await client.post(
            "/agent/tool/escalate",
            json={"session_id": session_id, "reason": "already escalating"},
        )
        assert third.status_code == 409


async def test_agent_turns_are_not_gated(fake_llm) -> None:
    set_mode(fake_llm["origin"], "valid")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = (await client.post("/api/session")).json()["session_id"]
        agent = await client.post(
            "/agent/transcript",
            json={
                "session_id": session_id,
                "speaker": "agent",
                "text": "Hi, I'm an AI calling on behalf of Alex Chen.",
            },
        )
        assert agent.status_code == 200
        blob = (await client.get(f"/api/session/{session_id}")).json()
        assert blob["verdicts"] == []
        assert blob["state"] == "CREATED"
        rep = await client.post(
            "/agent/transcript",
            json={
                "session_id": session_id,
                "speaker": "rep",
                "text": "Your confirmation number is ABC123. What would you like to do today?",
            },
        )
        assert rep.status_code == 200
        assert rep.json()["verdict"] == "ALLOW"
        blob = (await client.get(f"/api/session/{session_id}")).json()
        assert len(blob["verdicts"]) == 1


async def test_elevenlabs_webhook_ingests_user_transcript(fake_llm) -> None:
    set_mode(fake_llm["origin"], "valid")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = (await client.post("/api/session")).json()["session_id"]
        response = await client.post(
            "/agent/elevenlabs/event",
            json={
                "type": "user_transcript",
                "session_id": session_id,
                "conversation_id": "conv_test1",
                "user_transcription_event": {
                    "user_transcript": "Your confirmation number is ABC123."
                },
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["processed"] == 1
        assert body["verdicts"][0]["verdict"] == "ALLOW"
        blob = (await client.get(f"/api/session/{session_id}")).json()
        assert blob["transcripts"][0]["source"] == "elevenlabs"
        assert blob["transcripts"][0]["speaker"] == "rep"


async def test_elevenlabs_post_call_transcript_runs_gate(fake_llm) -> None:
    set_mode(fake_llm["origin"], "valid")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = (await client.post("/api/session")).json()["session_id"]
        response = await client.post(
            "/agent/elevenlabs/event",
            json={
                "type": "post_call_transcription",
                "data": {
                    "conversation_id": "conv_test2",
                    "conversation_initiation_client_data": {
                        "dynamic_variables": {"session_id": session_id}
                    },
                    "transcript": [
                        {"role": "agent", "message": "I'm an AI calling on behalf of Alex."},
                        {
                            "role": "user",
                            "message": "There is a two hundred dollar cancellation fee.",
                        },
                    ],
                },
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["processed"] == 2
        assert body["verdicts"][-1]["verdict"] == "ESCALATE"
        blob = (await client.get(f"/api/session/{session_id}")).json()
        assert blob["state"] == "ESCALATING"
