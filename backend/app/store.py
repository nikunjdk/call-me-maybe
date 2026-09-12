from uuid import uuid4

from fastapi import HTTPException

from app.models import (
    Extracted,
    Plan,
    PolicyVerdict,
    Session,
    SessionState,
    Summary,
)

_TERMINAL_AGENT = {
    SessionState.ESCALATING,
    SessionState.HUMAN_CONTROL,
    SessionState.ENDED,
    SessionState.SUMMARIZED,
}

_sessions: dict[str, Session] = {}


def create_session() -> Session:
    session_id = uuid4().hex[:12]
    session = Session(session_id=session_id, state=SessionState.CREATED)
    _sessions[session_id] = session
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
    return session


def set_extracted(session_id: str, extracted: Extracted) -> Session:
    session = get_session(session_id)
    require_state(session, SessionState.CREATED)
    session.extracted = extracted
    session.state = SessionState.EXTRACTED
    return session


def set_plan(session_id: str, plan: Plan) -> Session:
    session = get_session(session_id)
    require_state(session, SessionState.EXTRACTED)
    session.plan = plan
    session.state = SessionState.PLAN_PENDING
    return session


def approve(session_id: str) -> Session:
    session = get_session(session_id)
    require_state(session, SessionState.PLAN_PENDING)
    session.state = SessionState.PLAN_APPROVED
    return session


def append_verdict(session_id: str, verdict: PolicyVerdict) -> Session:
    session = get_session(session_id)
    session.verdicts.append(verdict)
    return session


def agent_turns_blocked(session: Session) -> bool:
    return session.state in _TERMINAL_AGENT


def escalate(session_id: str, verdict: PolicyVerdict) -> Session:
    session = get_session(session_id)
    session.verdicts.append(verdict)
    if session.state not in _TERMINAL_AGENT:
        session.state = SessionState.ESCALATING
    return session


def set_summary(session_id: str, summary: Summary) -> Session:
    session = get_session(session_id)
    session.summary = summary
    return session
