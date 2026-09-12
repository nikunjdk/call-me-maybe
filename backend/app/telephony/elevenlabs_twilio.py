"""ElevenLabs register_call → TwiML for the agent conference leg."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.agent.settings import elevenlabs_agent_id, elevenlabs_api_key
from app.models import Session

logger = logging.getLogger(__name__)


def build_dynamic_variables(session: Session | None, session_id: str) -> dict[str, str]:
    """session_id + plan/extracted fields for ConvAI tools and prompt vars."""
    variables: dict[str, str] = {"session_id": session_id}
    if session is None:
        return variables

    if session.plan is not None:
        plan = session.plan
        variables.update(
            {
                "opening_script": plan.opening_script or "",
                "goal": plan.goal or "",
                "target_name": plan.target_name or "",
                "target_number": plan.target_number or "",
                "permitted_actions": "; ".join(plan.permitted_actions or []),
                "escalation_triggers": "; ".join(plan.escalation_triggers or []),
            }
        )

    if session.extracted is not None:
        extracted = session.extracted
        variables.update(
            {
                "passenger_name": extracted.passenger_name or "",
                "pnr": extracted.pnr or "",
                "airline": extracted.airline or "",
                "flight_number": extracted.flight_number or "",
                "flight_date": extracted.date or "",
                "route": extracted.route or "",
                "ticket_class": extracted.ticket_class or "",
            }
        )

    return {key: value for key, value in variables.items() if value is not None}


def register_agent_call_twiml(
    *,
    session_id: str,
    from_number: str,
    to_number: str,
    session: Session | None,
    direction: str = "inbound",
) -> str:
    """Call ElevenLabs conversational_ai.twilio.register_call; return TwiML XML."""
    api_key = elevenlabs_api_key()
    agent_id = elevenlabs_agent_id()
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY required for register_call")
    if not agent_id:
        raise RuntimeError(
            "ELEVENLABS_AGENT_ID required (or agent/config/agent.json agent_id)"
        )

    from elevenlabs import ElevenLabs

    client = ElevenLabs(api_key=api_key)
    dynamic_variables = build_dynamic_variables(session, session_id)
    initiation: dict[str, Any] = {"dynamic_variables": dynamic_variables}

    twiml = client.conversational_ai.twilio.register_call(
        agent_id=agent_id,
        from_number=from_number,
        to_number=to_number,
        direction=direction,  # type: ignore[arg-type]
        conversation_initiation_client_data=initiation,  # type: ignore[arg-type]
    )
    if twiml is None:
        raise RuntimeError("ElevenLabs register_call returned empty TwiML")
    if isinstance(twiml, bytes):
        return twiml.decode("utf-8")
    return str(twiml)


_CONV_ID = re.compile(r"conv(?:ersation)?[_-]?id=([A-Za-z0-9_-]+)", re.IGNORECASE)
_CONV_TOKEN = re.compile(r"\b(conv_[A-Za-z0-9_-]+)\b")


def conversation_id_from_twiml(twiml: str) -> str | None:
    """Best-effort parse of the conversation id ElevenLabs embeds in Stream TwiML."""
    match = _CONV_ID.search(twiml)
    if match:
        return match.group(1)
    for url in re.findall(r"wss://[^\"'\s<]+", twiml):
        parsed = urlparse(url.replace("&amp;", "&"))
        for key, values in parse_qs(parsed.query).items():
            if "conversation" in key.lower() and values:
                return values[0]
    token = _CONV_TOKEN.search(twiml)
    if token:
        return token.group(1)
    return None
