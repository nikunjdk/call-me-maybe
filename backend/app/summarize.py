"""Gemini post-call summary + attention metric from A's timestamps."""

from __future__ import annotations

import json
import logging

from app.canned import CANNED_SUMMARY
from app.llm.provider import generate_content, parse_json_object
from app.models import Session, Summary

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Summarize a completed customer-service phone call. Reply with JSON only: "
    '{"outcome":"","actions_taken":[],"open_items":[]}'
)


def attention_seconds(session: Session) -> tuple[int, int]:
    started = session.call_started_ts
    ended = session.call_ended_ts
    unmuted = session.human_unmuted_ts
    total = 0
    human = 0
    if started is not None and ended is not None and ended >= started:
        total = ended - started
    if unmuted is not None and ended is not None and ended >= unmuted:
        human = ended - unmuted
    return total, human


async def generate_summary(session: Session) -> Summary:
    total, human = attention_seconds(session)
    result = await generate_content(
        "EXTRACTOR",
        system=_SYSTEM,
        user=json.dumps(
            {
                "goal": session.plan.goal if session.plan else None,
                "extracted": session.extracted.model_dump() if session.extracted else None,
                "transcripts": session.transcripts[-40:],
                "escalated": any(v.verdict == "ESCALATE" for v in session.verdicts),
            }
        ),
        temperature=0,
        max_tokens=1024,
    )
    parsed = result.parsed or parse_json_object(result.text)
    if not parsed:
        logger.info("summary fallback canned ok=%s error=%s", result.ok, result.error)
        return CANNED_SUMMARY.model_copy(
            update={"total_call_seconds": total, "human_attention_seconds": human}
        )
    return Summary(
        outcome=str(parsed.get("outcome") or "call ended"),
        actions_taken=list(parsed.get("actions_taken") or []),
        open_items=list(parsed.get("open_items") or []),
        total_call_seconds=total,
        human_attention_seconds=human,
    )
