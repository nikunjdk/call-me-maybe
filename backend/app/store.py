from uuid import uuid4

from fastapi import HTTPException

from app.canned import CANNED_EXTRACTED, CANNED_PLAN
from app.db import load_sessions, persist_session_nowait
from app.models import (
    Extracted,
    Plan,
    PolicyVerdict,
    Session,
    SessionState,
    Summary,
)

DEMO_SESSION_ID = "demo-alex-chen"

_TERMINAL_AGENT = {
    SessionState.ESCALATING,
    SessionState.HUMAN_CONTROL,
    SessionState.ENDED,
    SessionState.SUMMARIZED,
}

_A_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.PLAN_APPROVED: {SessionState.DIALING},
    SessionState.DIALING: {SessionState.IN_CALL},
    SessionState.IN_CALL: {SessionState.ENDED, SessionState.HUMAN_CONTROL},
    SessionState.ESCALATING: {SessionState.HUMAN_CONTROL, SessionState.ENDED},
    SessionState.HUMAN_CONTROL: {SessionState.ENDED},
    SessionState.ENDED: {SessionState.SUMMARIZED},
}

_sessions: dict[str, Session] = {}


def _flush(session: Session) -> None:
    persist_session_nowait(session)


def seed_demo() -> Session:
    """Known demo start: Alex Chen / UA 482 cancel, waiting on Approve."""
    session = Session(
        session_id=DEMO_SESSION_ID,
        state=SessionState.PLAN_PENDING,
        extracted=CANNED_EXTRACTED,
        plan=CANNED_PLAN,
        verdicts=[],
        transcripts=[],
        summary=None,
        call_started_ts=None,
        human_unmuted_ts=None,
        call_ended_ts=None,
    )
    _sessions[DEMO_SESSION_ID] = session
    _flush(session)
    return session


async def hydrate() -> int:
    for session in await load_sessions():
        if session.session_id == DEMO_SESSION_ID:
            continue
        if session.session_id not in _sessions:
            _sessions[session.session_id] = session
    seed_demo()
    return len(_sessions)


def create_session() -> Session:
    session_id = uuid4().hex[:12]
    session = Session(session_id=session_id, state=SessionState.CREATED)
    _sessions[session_id] = session
    _flush(session)
    return session


def get_session_or_none(session_id: str) -> Session | None:
    return _sessions.get(session_id)


def get_session(session_id: str) -> Session:
    session = get_session_or_none(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


def require_state(session: Session, expected: SessionState) -> None:
    if session.state != expected:
        raise HTTPException(
            status_code=409,
            detail=f"illegal transition: state is {session.state.value}, expected {expected.value}",
        )


def set_state(session_id: str, state: SessionState) -> Session:
    session = get_session(session_id)
    session.state = state
    _flush(session)
    return session


def patch_state(session_id: str, state: SessionState) -> Session:
    session = get_session(session_id)
    allowed = _A_TRANSITIONS.get(session.state, set())
    if state not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"illegal transition: {session.state.value} → {state.value}",
        )
    session.state = state
    _flush(session)
    return session


def set_extracted(session_id: str, extracted: Extracted) -> Session:
    session = get_session(session_id)
    require_state(session, SessionState.CREATED)
    session.extracted = extracted
    session.state = SessionState.EXTRACTED
    _flush(session)
    return session


def set_plan(session_id: str, plan: Plan) -> Session:
    session = get_session(session_id)
    require_state(session, SessionState.EXTRACTED)
    session.plan = plan
    session.state = SessionState.PLAN_PENDING
    _flush(session)
    return session


def approve(session_id: str) -> Session:
    session = get_session(session_id)
    require_state(session, SessionState.PLAN_PENDING)
    session.state = SessionState.PLAN_APPROVED
    _flush(session)
    return session


def append_verdict(session_id: str, verdict: PolicyVerdict) -> Session:
    session = get_session(session_id)
    session.verdicts.append(verdict)
    _flush(session)
    return session


def append_transcript(session_id: str, speaker: str, text: str) -> Session:
    session = get_session(session_id)
    session.transcripts.append({"speaker": speaker, "text": text})
    _flush(session)
    return session


def set_timestamps(
    session_id: str,
    *,
    call_started_ts: int | None = None,
    human_unmuted_ts: int | None = None,
    call_ended_ts: int | None = None,
) -> Session:
    session = get_session(session_id)
    if call_started_ts is not None:
        session.call_started_ts = call_started_ts
    if human_unmuted_ts is not None:
        session.human_unmuted_ts = human_unmuted_ts
    if call_ended_ts is not None:
        session.call_ended_ts = call_ended_ts
    _flush(session)
    return session


def agent_turns_blocked(session: Session) -> bool:
    return session.state in _TERMINAL_AGENT


def escalate(session_id: str, verdict: PolicyVerdict) -> Session:
    session = get_session(session_id)
    session.verdicts.append(verdict)
    if session.state not in _TERMINAL_AGENT:
        session.state = SessionState.ESCALATING
    _flush(session)
    return session


def set_summary(session_id: str, summary: Summary) -> Session:
    session = get_session(session_id)
    session.summary = summary
    session.state = SessionState.SUMMARIZED
    _flush(session)
    return session
