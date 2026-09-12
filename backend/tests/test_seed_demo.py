from app.models import SessionState
from app.store import DEMO_SESSION_ID, get_session, seed_demo


def test_seed_demo_is_plan_pending() -> None:
    session = seed_demo()
    assert session.session_id == DEMO_SESSION_ID
    assert session.state == SessionState.PLAN_PENDING
    assert session.extracted is not None
    assert session.extracted.pnr == "ABC123"
    assert session.plan is not None
    loaded = get_session(DEMO_SESSION_ID)
    assert loaded.state == SessionState.PLAN_PENDING
