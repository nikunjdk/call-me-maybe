"""Grok call-plan generation. Falls back to canned on failure."""

from __future__ import annotations

import json
import logging
import os

from app.canned import canned_plan
from app.llm.provider import chat, parse_json_object
from app.models import Extracted, Plan

logger = logging.getLogger(__name__)


def _demo_dest() -> str:
    """Hack-demo override so Approve rings the verified phone, not 1-800."""
    return (
        os.getenv("TWILIO_SIM_REP_NUMBER", "").strip()
        or os.getenv("TWILIO_LIVE_REP_NUMBER", "").strip()
    )


def _stamp_dest(plan: Plan) -> Plan:
    dest = _demo_dest()
    if dest:
        return plan.model_copy(update={"target_number": dest})
    return plan


_SYSTEM = (
    "Write a phone-call plan for an AI agent that will cancel or change a booking. "
    "The agent may only identify itself as AI, state the approved request, supply "
    "booking references, and answer from the extracted document. Reply with JSON: "
    '{"goal":"","target_name":"","target_number":"","opening_script":"",'
    '"permitted_actions":[],"escalation_triggers":[],"estimated_duration":""}'
)


async def generate_plan(extracted: Extracted, goal: str) -> tuple[Plan, bool]:
    result = await chat(
        "PLANNER",
        [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": json.dumps({"goal": goal, "extracted": extracted.model_dump()}),
            },
        ],
        temperature=0.2,
        max_tokens=700,
    )
    parsed = result.parsed or parse_json_object(result.text)
    if not parsed:
        logger.info("planner fallback canned ok=%s error=%s", result.ok, result.error)
        return _stamp_dest(canned_plan(goal, extracted)), True
    try:
        plan = Plan(
            goal=str(parsed.get("goal") or goal),
            target_name=str(parsed.get("target_name") or ""),
            target_number=str(parsed.get("target_number") or ""),
            opening_script=str(parsed.get("opening_script") or ""),
            permitted_actions=list(parsed.get("permitted_actions") or []),
            escalation_triggers=list(parsed.get("escalation_triggers") or []),
            estimated_duration=str(parsed.get("estimated_duration") or ""),
        )
    except Exception:
        return _stamp_dest(canned_plan(goal, extracted)), True
    if not plan.opening_script or not plan.target_name:
        return _stamp_dest(canned_plan(goal, extracted)), True
    return _stamp_dest(plan), False
