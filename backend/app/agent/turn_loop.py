"""Per-turn transcript + verdict handling for the voice agent loop."""

from __future__ import annotations

from typing import Any

from app.agent.client import post_escalate, post_transcript

STALL_PHRASE = (
    "One moment please — I'm connecting the account holder now, "
    "they'll be right with you."
)


async def on_turn_complete(
    session_id: str,
    speaker: str,
    text: str,
) -> dict[str, Any]:
    """Post a completed turn; if gate says ESCALATE, stop further agent speech.

    Returns {"verdict": ..., "block_agent": bool, "stall_phrase": str | None}.
    """
    verdict = await post_transcript(session_id, speaker, text)
    if verdict.get("verdict") == "ESCALATE":
        return {
            "verdict": verdict,
            "block_agent": True,
            "stall_phrase": STALL_PHRASE,
        }
    return {"verdict": verdict, "block_agent": False, "stall_phrase": None}


async def escalate_now(session_id: str, reason: str) -> dict[str, Any]:
    """Agent decided to escalate via tool — POST then stall."""
    verdict = await post_escalate(session_id, reason)
    return {
        "verdict": verdict,
        "block_agent": True,
        "stall_phrase": STALL_PHRASE,
    }
