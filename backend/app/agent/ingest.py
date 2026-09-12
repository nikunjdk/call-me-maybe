"""Turn ingest used by /agent/transcript, ElevenLabs webhooks, and the live poller."""

from __future__ import annotations

import logging

from fastapi import HTTPException

from app.canned import canned_escalate
from app.db import persist_verdict
from app.events import emit_event, emit_state
from app.models import PolicyVerdict, Speaker
from app.policy.gate import classify
from app.store import (
    agent_turns_blocked,
    append_transcript,
    append_verdict,
    escalate,
    get_session,
)

logger = logging.getLogger(__name__)


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _passthrough() -> PolicyVerdict:
    return PolicyVerdict(
        verdict="ALLOW",
        trigger="none",
        reason="agent/user turn — gate classifies representative utterances only",
        confidence=1.0,
        tier=1,
        latency_ms=0,
        tier1_latency_ms=0,
        tier2_latency_ms=None,
        provider_label="gate",
        degraded=False,
        notes=["not gated"],
    )


def already_recorded(session_id: str, speaker: str, text: str) -> bool:
    session = get_session(session_id)
    needle = _norm(text)
    for turn in reversed(session.transcripts[-12:]):
        if turn.get("speaker") == speaker and _norm(str(turn.get("text") or "")) == needle:
            return True
    return False


async def ingest_transcript(
    session_id: str,
    speaker: Speaker,
    text: str,
    source: str | None = None,
) -> PolicyVerdict:
    session = get_session(session_id)
    blocked = agent_turns_blocked(session)

    if already_recorded(session_id, speaker, text):
        if session.verdicts:
            return session.verdicts[-1]
        return _passthrough()

    payload: dict = {"speaker": speaker, "text": text}
    if source:
        payload["source"] = source
    logger.info(
        "transcript session_id=%s speaker=%s source=%s text=%s",
        session_id,
        speaker,
        source or "direct",
        text[:160],
    )
    await emit_event(session_id, "transcript_turn", payload)
    append_transcript(session_id, speaker, text, source=source)

    # After ESCALATE: still record the stall / leftover audio, never re-open the agent.
    if blocked:
        if session.verdicts:
            return session.verdicts[-1]
        return canned_escalate("already escalating")

    if speaker != "rep":
        return _passthrough()

    verdict = await classify(text)
    if verdict.verdict == "ESCALATE":
        session = escalate(session_id, verdict)
        await emit_event(session_id, "policy_verdict", verdict.model_dump())
        await emit_event(
            session_id,
            "escalation",
            {"reason": verdict.reason, "verdict": verdict.model_dump()},
        )
        await emit_state(session_id, session.state)
        await persist_verdict(session_id, verdict)
        return verdict

    append_verdict(session_id, verdict)
    await emit_event(session_id, "policy_verdict", verdict.model_dump())
    await persist_verdict(session_id, verdict)
    return verdict


async def ingest_tool_escalate(session_id: str, reason: str) -> PolicyVerdict:
    session = get_session(session_id)
    if agent_turns_blocked(session):
        raise HTTPException(
            status_code=409,
            detail="no further agent turns after ESCALATE",
        )
    verdict = canned_escalate(reason)
    session = escalate(session_id, verdict)
    await emit_event(session_id, "policy_verdict", verdict.model_dump())
    await emit_event(
        session_id,
        "escalation",
        {"reason": reason, "verdict": verdict.model_dump()},
    )
    await emit_state(session_id, session.state)
    await persist_verdict(session_id, verdict)
    return verdict
