from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SessionState(str, Enum):
    CREATED = "CREATED"
    EXTRACTED = "EXTRACTED"
    PLAN_PENDING = "PLAN_PENDING"
    PLAN_APPROVED = "PLAN_APPROVED"
    DIALING = "DIALING"
    IN_CALL = "IN_CALL"
    ESCALATING = "ESCALATING"
    HUMAN_CONTROL = "HUMAN_CONTROL"
    ENDED = "ENDED"
    SUMMARIZED = "SUMMARIZED"


Trigger = Literal["money", "authorization", "identity", "ambiguity", "none"]
Verdict = Literal["ALLOW", "ESCALATE"]
Speaker = Literal["rep", "agent", "user"]
EventType = Literal[
    "state_changed",
    "transcript_turn",
    "policy_verdict",
    "escalation",
    "summary_ready",
]


class Extracted(BaseModel):
    passenger_name: str
    pnr: str
    airline: str
    flight_number: str
    date: str
    route: str
    ticket_class: str


class Plan(BaseModel):
    goal: str
    target_name: str
    target_number: str
    opening_script: str
    permitted_actions: list[str] = Field(default_factory=list)
    escalation_triggers: list[str] = Field(default_factory=list)
    estimated_duration: str


class PolicyVerdict(BaseModel):
    verdict: Verdict
    trigger: Trigger
    reason: str
    confidence: float
    tier: Literal[0, 1, 2]
    latency_ms: int
    tier1_latency_ms: int
    tier2_latency_ms: int | None = None
    provider_label: str
    degraded: bool = False
    notes: list[str] = Field(default_factory=list)


class Summary(BaseModel):
    outcome: str
    actions_taken: list[str] = Field(default_factory=list)
    open_items: list[str] = Field(default_factory=list)
    total_call_seconds: int = 0
    human_attention_seconds: int = 0


class Session(BaseModel):
    session_id: str
    state: SessionState
    extracted: Extracted | None = None
    plan: Plan | None = None
    summary: Summary | None = None
    verdicts: list[PolicyVerdict] = Field(default_factory=list)


class EventEnvelope(BaseModel):
    type: EventType
    session_id: str
    ts: int
    data: dict


class SessionCreateResponse(BaseModel):
    session_id: str


class ApproveResponse(BaseModel):
    session_id: str
    state: SessionState


class PlanRequest(BaseModel):
    goal: str = "cancel this flight"


class TranscriptRequest(BaseModel):
    session_id: str
    speaker: Speaker
    text: str


class EscalateRequest(BaseModel):
    session_id: str
    reason: str
