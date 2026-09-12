from app.models import Session, SessionState
from app.summarize import attention_seconds


def test_attention_metric_from_timestamps() -> None:
    session = Session(
        session_id="s",
        state=SessionState.ENDED,
        call_started_ts=1_000,
        human_unmuted_ts=1_040,
        call_ended_ts=1_100,
    )
    total, human = attention_seconds(session)
    assert total == 100
    assert human == 60


def test_attention_zero_without_clock() -> None:
    session = Session(session_id="s", state=SessionState.CREATED)
    assert attention_seconds(session) == (0, 0)
