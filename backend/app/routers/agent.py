from fastapi import APIRouter, HTTPException

from app.canned import canned_escalate
from app.events import emit_event, emit_state
from app.models import EscalateRequest, PolicyVerdict, TranscriptRequest
from app.policy.gate import classify
from app.store import agent_turns_blocked, append_verdict, escalate, get_session

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/transcript", response_model=PolicyVerdict)
async def post_transcript(body: TranscriptRequest) -> PolicyVerdict:
    session = get_session(body.session_id)
    if agent_turns_blocked(session):
        raise HTTPException(
            status_code=409,
            detail="no further agent turns after ESCALATE",
        )
    await emit_event(
        body.session_id,
        "transcript_turn",
        {"speaker": body.speaker, "text": body.text},
    )
    verdict = await classify(body.text)
    if verdict.verdict == "ESCALATE":
        session = escalate(body.session_id, verdict)
        await emit_event(
            body.session_id,
            "policy_verdict",
            verdict.model_dump(),
        )
        await emit_event(
            body.session_id,
            "escalation",
            {"reason": verdict.reason, "verdict": verdict.model_dump()},
        )
        await emit_state(body.session_id, session.state)
        return verdict
    append_verdict(body.session_id, verdict)
    await emit_event(body.session_id, "policy_verdict", verdict.model_dump())
    return verdict


@router.post("/tool/escalate", response_model=PolicyVerdict)
async def post_escalate(body: EscalateRequest) -> PolicyVerdict:
    session = get_session(body.session_id)
    verdict = canned_escalate(body.reason)
    session = escalate(body.session_id, verdict)
    await emit_event(body.session_id, "escalation", {"reason": body.reason, "verdict": verdict.model_dump()})
    await emit_state(body.session_id, session.state)
    return verdict
