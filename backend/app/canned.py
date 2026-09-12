from app.models import Extracted, Plan, PolicyVerdict, Summary

CANNED_EXTRACTED = Extracted(
    passenger_name="Alex Chen",
    pnr="ABC123",
    airline="United",
    flight_number="UA 482",
    date="2026-09-18",
    route="SFO → JFK",
    ticket_class="Economy",
)

CANNED_PLAN = Plan(
    goal="Cancel this flight and request a refund to the original form of payment.",
    target_name="United Airlines Reservations",
    target_number="+1-800-864-8331",
    opening_script=(
        "Hello, this is an AI assistant calling on behalf of Alex Chen. "
        "I have their booking reference ABC123 for United flight UA 482 on "
        "September 18 from San Francisco to New York. They would like to cancel "
        "this reservation."
    ),
    permitted_actions=[
        "identify as AI",
        "state the approved cancel request",
        "supply booking references",
        "answer from the extracted document",
    ],
    escalation_triggers=["money", "authorization", "identity", "ambiguity"],
    estimated_duration="4 minutes",
)

CANNED_SUMMARY = Summary(
    outcome="stub — summary not generated yet",
    actions_taken=[],
    open_items=[],
    total_call_seconds=0,
    human_attention_seconds=0,
)

CANNED_ALLOW = PolicyVerdict(
    verdict="ALLOW",
    trigger="none",
    reason="stub gate — canned ALLOW (real classifier not wired yet)",
    confidence=0.99,
    tier=1,
    latency_ms=0,
    tier1_latency_ms=0,
    tier2_latency_ms=None,
    provider_label="stub",
    degraded=False,
    notes=["hour-one canned verdict"],
)


def canned_plan(goal: str) -> Plan:
    if not goal.strip():
        return CANNED_PLAN
    return CANNED_PLAN.model_copy(update={"goal": goal})


def canned_escalate(reason: str) -> PolicyVerdict:
    return PolicyVerdict(
        verdict="ESCALATE",
        trigger="ambiguity",
        reason=reason,
        confidence=1.0,
        tier=0,
        latency_ms=0,
        tier1_latency_ms=0,
        tier2_latency_ms=None,
        provider_label="stub",
        degraded=False,
        notes=["hour-one canned escalate"],
    )
