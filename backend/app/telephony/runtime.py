from __future__ import annotations

import time
from dataclasses import dataclass, field

CONFERENCE_PREFIX = "cmm-"
IDENTITY_PREFIX = "user-"


def conference_name(session_id: str) -> str:
    return f"{CONFERENCE_PREFIX}{session_id}"


def client_identity(session_id: str) -> str:
    return f"{IDENTITY_PREFIX}{session_id}"


def session_id_from_conference(name: str | None) -> str | None:
    if not name:
        return None
    if name.startswith(CONFERENCE_PREFIX):
        return name[len(CONFERENCE_PREFIX) :]
    return None


def session_id_from_identity(identity: str | None) -> str | None:
    if not identity:
        return None
    value = identity
    if value.startswith("client:"):
        value = value[len("client:") :]
    if value.startswith(IDENTITY_PREFIX):
        return value[len(IDENTITY_PREFIX) :]
    return None


@dataclass
class CallRuntime:
    session_id: str
    conference: str
    conference_sid: str | None = None
    rep_call_sid: str | None = None
    agent_call_sid: str | None = None
    browser_call_sid: str | None = None
    dialing_ts: int = field(default_factory=lambda: int(time.time()))
    in_call_ts: int | None = None
    unmuted_ts: int | None = None
    ended_ts: int | None = None

    def mark_in_call(self) -> None:
        if self.in_call_ts is None:
            self.in_call_ts = int(time.time())

    def mark_unmuted(self) -> int:
        self.unmuted_ts = int(time.time())
        return self.unmuted_ts

    def mark_ended(self) -> int:
        self.ended_ts = int(time.time())
        return self.ended_ts

    def timestamp_data(self) -> dict:
        data: dict = {}
        if self.in_call_ts is not None:
            data["call_started_ts"] = self.in_call_ts
        if self.unmuted_ts is not None:
            data["leg_c_unmuted_ts"] = self.unmuted_ts
        if self.ended_ts is not None:
            data["call_ended_ts"] = self.ended_ts
        return data


_by_session: dict[str, CallRuntime] = {}
_active: CallRuntime | None = None


def start_call(session_id: str) -> CallRuntime:
    global _active
    runtime = CallRuntime(
        session_id=session_id,
        conference=conference_name(session_id),
    )
    _by_session[session_id] = runtime
    _active = runtime
    return runtime


def get_runtime(session_id: str) -> CallRuntime | None:
    return _by_session.get(session_id)


def get_active() -> CallRuntime | None:
    return _active


def remember_call_sid(runtime: CallRuntime, label: str, call_sid: str | None) -> None:
    if not call_sid:
        return
    if label == "rep":
        runtime.rep_call_sid = call_sid
    elif label == "agent":
        runtime.agent_call_sid = call_sid
    elif label == "browser":
        runtime.browser_call_sid = call_sid


def reset_for_tests() -> None:
    global _active
    _by_session.clear()
    _active = None
