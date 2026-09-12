from fastapi import APIRouter, HTTPException, Request

from app.canned import canned_escalate
from app.db import persist_verdict
from app.events import emit_event, emit_state
from app.models import EscalateRequest, PolicyVerdict, Speaker, TranscriptRequest
from app.policy.gate import classify
from app.store import agent_turns_blocked, append_transcript, append_verdict, escalate, get_session

router = APIRouter(prefix="/agent", tags=["agent"])

_SPEAKER_MAP = {
    "agent": "agent",
    "assistant": "agent",
    "user": "rep",
    "rep": "rep",
    "customer": "rep",
    "human": "user",
}


async def _ingest_transcript(session_id: str, speaker: Speaker, text: str) -> PolicyVerdict:
    session = get_session(session_id)
    if agent_turns_blocked(session):
        raise HTTPException(
            status_code=409,
            detail="no further agent turns after ESCALATE",
        )
    await emit_event(
        session_id,
        "transcript_turn",
        {"speaker": speaker, "text": text},
    )
    append_transcript(session_id, speaker, text)
    verdict = await classify(text)
    if verdict.verdict == "ESCALATE":
        session = escalate(session_id, verdict)
        await emit_event(
            session_id,
            "policy_verdict",
            verdict.model_dump(),
        )
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


def _session_id_from_payload(payload: dict) -> str | None:
    direct = payload.get("session_id")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    data = payload.get("data")
    if isinstance(data, dict):
        nested = data.get("session_id")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
        init = data.get("conversation_initiation_client_data")
        if isinstance(init, dict):
            dyn = init.get("dynamic_variables")
            if isinstance(dyn, dict):
                sid = dyn.get("session_id")
                if isinstance(sid, str) and sid.strip():
                    return sid.strip()

    init = payload.get("conversation_initiation_client_data")
    if isinstance(init, dict):
        dyn = init.get("dynamic_variables")
        if isinstance(dyn, dict):
            sid = dyn.get("session_id")
            if isinstance(sid, str) and sid.strip():
                return sid.strip()

    dyn = payload.get("dynamic_variables")
    if isinstance(dyn, dict):
        sid = dyn.get("session_id")
        if isinstance(sid, str) and sid.strip():
            return sid.strip()
    return None


def _map_speaker(role: str | None) -> Speaker | None:
    if not role:
        return None
    mapped = _SPEAKER_MAP.get(role.strip().lower())
    if mapped in ("agent", "rep", "user"):
        return mapped  # type: ignore[return-value]
    return None


@router.post("/transcript", response_model=PolicyVerdict)
async def post_transcript(body: TranscriptRequest) -> PolicyVerdict:
    return await _ingest_transcript(body.session_id, body.speaker, body.text)


@router.post("/tool/escalate", response_model=PolicyVerdict)
async def post_escalate(body: EscalateRequest) -> PolicyVerdict:
    session = get_session(body.session_id)
    if agent_turns_blocked(session):
        raise HTTPException(
            status_code=409,
            detail="no further agent turns after ESCALATE",
        )
    verdict = canned_escalate(body.reason)
    session = escalate(body.session_id, verdict)
    await emit_event(body.session_id, "escalation", {"reason": body.reason, "verdict": verdict.model_dump()})
    await emit_state(body.session_id, session.state)
    await persist_verdict(body.session_id, verdict)
    return verdict


@router.post("/elevenlabs/event")
async def post_elevenlabs_event(request: Request) -> dict:
    """Map ElevenLabs conversation / transcript webhooks into C's gate.

    Accepts:
    - Contract turn: {session_id, speaker, text}
    - Live-ish events: {type: user_transcript|agent_response, session_id, text|...}
    - post_call_transcription: full transcript list under data.transcript
    """
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="JSON body required") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON object required")

    session_id = _session_id_from_payload(payload)
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="session_id required (body or dynamic_variables)",
        )
    get_session(session_id)

    event_type = str(payload.get("type") or payload.get("event_type") or "").lower()
    verdicts: list[dict] = []

    # Direct contract-shaped turn
    text = payload.get("text")
    speaker = _map_speaker(str(payload.get("speaker") or ""))
    if isinstance(text, str) and text.strip() and speaker:
        verdict = await _ingest_transcript(session_id, speaker, text.strip())
        return {"ok": True, "processed": 1, "verdicts": [verdict.model_dump()]}

    # Live client-style events
    if event_type in {"user_transcript", "tentative_user_transcript"}:
        ute = payload.get("user_transcription_event") or {}
        message = (
            payload.get("text")
            or payload.get("user_transcript")
            or (ute.get("user_transcript") if isinstance(ute, dict) else None)
        )
        if isinstance(message, str) and message.strip():
            verdict = await _ingest_transcript(session_id, "rep", message.strip())
            return {"ok": True, "processed": 1, "verdicts": [verdict.model_dump()]}

    if event_type in {"agent_response", "agent_response_correction"}:
        are = payload.get("agent_response_event") or payload.get(
            "agent_response_correction_event"
        ) or {}
        message = (
            payload.get("text")
            or payload.get("agent_response")
            or (
                are.get("agent_response")
                if isinstance(are, dict)
                else None
            )
            or (
                are.get("corrected_agent_response")
                if isinstance(are, dict)
                else None
            )
        )
        if isinstance(message, str) and message.strip():
            verdict = await _ingest_transcript(session_id, "agent", message.strip())
            return {"ok": True, "processed": 1, "verdicts": [verdict.model_dump()]}

    # Post-call transcription webhook
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    transcript = data.get("transcript") if isinstance(data, dict) else None
    if isinstance(transcript, list):
        for turn in transcript:
            if not isinstance(turn, dict):
                continue
            role = _map_speaker(str(turn.get("role") or turn.get("speaker") or ""))
            message = turn.get("message") or turn.get("text")
            if not role or not isinstance(message, str) or not message.strip():
                continue
            try:
                verdict = await _ingest_transcript(session_id, role, message.strip())
                verdicts.append(verdict.model_dump())
            except HTTPException as exc:
                if exc.status_code == 409:
                    break
                raise
        return {"ok": True, "processed": len(verdicts), "verdicts": verdicts}

    return {"ok": True, "processed": 0, "verdicts": []}
