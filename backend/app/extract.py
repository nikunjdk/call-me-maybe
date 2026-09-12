"""Gemini booking extraction. Falls back to canned on failure (T-4 ladder)."""

from __future__ import annotations

import logging

from app.canned import CANNED_EXTRACTED
from app.llm.provider import chat, parse_json_object
from app.models import Extracted

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Extract a flight booking from the document text. Reply with a single JSON "
    "object and nothing else: "
    '{"passenger_name":"","pnr":"","airline":"","flight_number":"","date":"",'
    '"route":"","ticket_class":""}'
)


def _from_parsed(parsed: dict) -> Extracted | None:
    try:
        return Extracted(
            passenger_name=str(parsed.get("passenger_name") or "").strip(),
            pnr=str(parsed.get("pnr") or "").strip(),
            airline=str(parsed.get("airline") or "").strip(),
            flight_number=str(parsed.get("flight_number") or "").strip(),
            date=str(parsed.get("date") or "").strip(),
            route=str(parsed.get("route") or "").strip(),
            ticket_class=str(parsed.get("ticket_class") or "").strip(),
        )
    except Exception:
        return None


async def extract_booking(document_text: str) -> tuple[Extracted, bool]:
    """Return (extracted, used_canned_fallback)."""
    result = await chat(
        "EXTRACTOR",
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": document_text[:8000] or "(empty upload)"},
        ],
        temperature=0,
        max_tokens=400,
    )
    parsed = result.parsed or parse_json_object(result.text)
    extracted = _from_parsed(parsed) if parsed else None
    if extracted is None or not extracted.pnr:
        logger.info("extractor fallback canned ok=%s error=%s", result.ok, result.error)
        return CANNED_EXTRACTED, True
    return extracted, False
