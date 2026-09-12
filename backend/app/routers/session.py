import logging

from fastapi import APIRouter, HTTPException, UploadFile

from app.events import emit_event, emit_state
from app.extract import extract_booking, sniff_upload
from app.models import (
    ApproveResponse,
    Extracted,
    Plan,
    PlanRequest,
    Session,
    SessionCreateResponse,
    SessionState,
    StatePatchRequest,
    Summary,
    TimestampsRequest,
)
from app.planner import generate_plan
from app.store import (
    approve,
    create_session,
    get_session,
    patch_state,
    set_extracted,
    set_plan,
    set_summary,
    set_timestamps,
)
from app.summarize import generate_summary
from app.telephony.router import dial as start_dial

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/session", tags=["session"])


@router.post("", response_model=SessionCreateResponse)
async def post_session() -> SessionCreateResponse:
    session = create_session()
    await emit_state(session.session_id, session.state)
    return SessionCreateResponse(session_id=session.session_id)


@router.post("/{session_id}/document", response_model=Extracted)
async def post_document(session_id: str, file: UploadFile) -> Extracted:
    raw = await file.read()
    text, file_bytes, mime_type = sniff_upload(raw, file.filename, file.content_type)
    extracted, fallback = await extract_booking(
        text, file_bytes=file_bytes, mime_type=mime_type
    )
    if fallback:
        logger.info("document extract used canned fallback session_id=%s", session_id)
    session = set_extracted(session_id, extracted)
    await emit_state(session_id, session.state)
    return session.extracted


@router.post("/{session_id}/plan", response_model=Plan)
async def post_plan(session_id: str, body: PlanRequest | None = None) -> Plan:
    goal = body.goal if body else "cancel this flight"
    session = get_session(session_id)
    if session.extracted is None:
        raise HTTPException(status_code=409, detail="extract a document first")
    plan, fallback = await generate_plan(session.extracted, goal)
    if fallback:
        logger.info("plan used canned fallback session_id=%s", session_id)
    session = set_plan(session_id, plan)
    await emit_state(session_id, session.state)
    return session.plan


@router.post("/{session_id}/approve", response_model=ApproveResponse)
async def post_approve(session_id: str) -> ApproveResponse:
    session = approve(session_id)
    await emit_state(session_id, session.state)
    try:
        await start_dial(session_id)
    except HTTPException as exc:
        if exc.status_code == 503:
            logger.info("A /dial skipped (Twilio unset) session_id=%s", session_id)
        elif exc.status_code == 502:
            logger.warning("A /dial failed session_id=%s", session_id, exc_info=True)
            raise
        else:
            logger.warning(
                "A /dial HTTP %s session_id=%s",
                exc.status_code,
                session_id,
                exc_info=True,
            )
    except Exception:
        logger.warning("A /dial failed session_id=%s", session_id, exc_info=True)
        raise HTTPException(status_code=502, detail="twilio dial failed") from None
    session = get_session(session_id)
    return ApproveResponse(session_id=session_id, state=session.state)


@router.post("/{session_id}/state", response_model=ApproveResponse)
async def post_state(session_id: str, body: StatePatchRequest) -> ApproveResponse:
    session = patch_state(session_id, body.state)
    await emit_state(session_id, session.state)
    return ApproveResponse(session_id=session_id, state=session.state)


@router.post("/{session_id}/timestamps", response_model=Session)
async def post_timestamps(session_id: str, body: TimestampsRequest) -> Session:
    return set_timestamps(
        session_id,
        call_started_ts=body.call_started_ts,
        human_unmuted_ts=body.human_unmuted_ts,
        call_ended_ts=body.call_ended_ts,
    )


@router.get("/{session_id}", response_model=Session)
async def get_session_blob(session_id: str) -> Session:
    return get_session(session_id)


_SUMMARY_STATES = {
    SessionState.ENDED,
    SessionState.SUMMARIZED,
}


@router.get("/{session_id}/summary", response_model=Summary)
async def get_summary(session_id: str) -> Summary:
    session = get_session(session_id)
    if session.summary is not None:
        return session.summary
    if session.state not in _SUMMARY_STATES:
        raise HTTPException(
            status_code=409,
            detail="summary available after the call ends",
        )
    summary = await generate_summary(session)
    session = set_summary(session_id, summary)
    await emit_event(session_id, "summary_ready", summary.model_dump())
    await emit_state(session_id, session.state)
    return session.summary
