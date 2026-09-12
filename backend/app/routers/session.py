import logging

from fastapi import APIRouter, UploadFile

from app.canned import CANNED_EXTRACTED, CANNED_SUMMARY, canned_plan
from app.events import emit_state
from app.models import (
    ApproveResponse,
    Extracted,
    Plan,
    PlanRequest,
    Session,
    SessionCreateResponse,
    Summary,
)
from app.store import (
    approve,
    create_session,
    get_session,
    set_extracted,
    set_plan,
    set_summary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/session", tags=["session"])


@router.post("", response_model=SessionCreateResponse)
async def post_session() -> SessionCreateResponse:
    session = create_session()
    await emit_state(session.session_id, session.state)
    return SessionCreateResponse(session_id=session.session_id)


@router.post("/{session_id}/document", response_model=Extracted)
async def post_document(session_id: str, file: UploadFile) -> Extracted:
    _ = await file.read()
    session = set_extracted(session_id, CANNED_EXTRACTED)
    await emit_state(session_id, session.state)
    return session.extracted


@router.post("/{session_id}/plan", response_model=Plan)
async def post_plan(session_id: str, body: PlanRequest | None = None) -> Plan:
    goal = body.goal if body else "cancel this flight"
    session = set_plan(session_id, canned_plan(goal))
    await emit_state(session_id, session.state)
    return session.plan


@router.post("/{session_id}/approve", response_model=ApproveResponse)
async def post_approve(session_id: str) -> ApproveResponse:
    session = approve(session_id)
    logger.info("A /dial goes here session_id=%s (not wired in hour one)", session_id)
    await emit_state(session_id, session.state)
    return ApproveResponse(session_id=session_id, state=session.state)


@router.get("/{session_id}", response_model=Session)
async def get_session_blob(session_id: str) -> Session:
    return get_session(session_id)


@router.get("/{session_id}/summary", response_model=Summary)
async def get_summary(session_id: str) -> Summary:
    session = get_session(session_id)
    if session.summary is None:
        set_summary(session_id, CANNED_SUMMARY)
        session = get_session(session_id)
    return session.summary
