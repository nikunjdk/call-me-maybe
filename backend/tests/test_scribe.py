import httpx

from app.main import app
from app.telephony.scribe import committed_text, ingest_scribe_turn
from tests.conftest import set_mode


def test_committed_text_from_nested_payload() -> None:
    assert committed_text({"text": "hello there"}) == "hello there"
    assert (
        committed_text({"committed_transcript_event": {"text": " fee line "}})
        == "fee line"
    )
    assert committed_text("plain") == "plain"
    assert committed_text({}) == ""


async def test_scribe_turn_runs_hard_net(fake_llm) -> None:
    set_mode(fake_llm["origin"], "allow_money")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = (await client.post("/api/session")).json()["session_id"]
        await ingest_scribe_turn(
            session_id,
            "rep",
            "Please note there is a two hundred dollar cancellation fee.",
        )
        blob = (await client.get(f"/api/session/{session_id}")).json()
        assert blob["transcripts"][0]["source"] == "elevenlabs"
        assert blob["verdicts"][0]["verdict"] == "ESCALATE"
        assert blob["verdicts"][0]["tier"] == 0
        assert blob["state"] == "ESCALATING"
