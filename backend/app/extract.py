"""Booking extraction. LLM first; local PDF/text parse if the model fails.

Never substitute the Alex Chen demo stub for a real upload.
"""

from __future__ import annotations

import io
import logging
import re

from pypdf import PdfReader

from app.llm.provider import generate_content, parse_json_object
from app.models import Extracted

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Extract a flight booking from the ticket. Reply with a single JSON "
    "object and nothing else: "
    '{"passenger_name":"","pnr":"","airline":"","flight_number":"","date":"",'
    '"route":"","ticket_class":""}. '
    "pnr is the record locator / booking ref / confirmation code "
    "(not the e-ticket number). Passenger names may be LAST/FIRST. "
    "For multi-segment tickets use the first flight and the overall route. "
    "Use empty strings when unknown."
)

_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/heic",
    "image/heif",
}

_PNR_KEYS = (
    "pnr",
    "booking_ref",
    "booking_reference",
    "record_locator",
    "recordLocator",
    "confirmation",
    "confirmation_code",
    "confirmation_number",
    "locator",
)
_NAME_KEYS = ("passenger_name", "passenger", "name", "traveler", "traveller")
_FLIGHT_KEYS = ("flight_number", "flight", "flight_no")
_AIRLINE_KEYS = ("airline", "carrier", "airline_name")
_DATE_KEYS = ("date", "flight_date", "departure_date")
_ROUTE_KEYS = ("route", "itinerary")
_CLASS_KEYS = ("ticket_class", "cabin", "class")

_MONTHS = {
    "JAN": "01",
    "FEB": "02",
    "MAR": "03",
    "APR": "04",
    "MAY": "05",
    "JUN": "06",
    "JUL": "07",
    "AUG": "08",
    "SEP": "09",
    "OCT": "10",
    "NOV": "11",
    "DEC": "12",
}

_AIRLINES = {
    "JL": "Japan Airlines",
    "NH": "All Nippon Airways",
    "UA": "United",
    "AA": "American Airlines",
    "DL": "Delta",
    "BA": "British Airways",
    "AF": "Air France",
    "LH": "Lufthansa",
    "EK": "Emirates",
    "QR": "Qatar Airways",
    "SQ": "Singapore Airlines",
    "CX": "Cathay Pacific",
    "AC": "Air Canada",
    "WN": "Southwest",
    "B6": "JetBlue",
    "AS": "Alaska Airlines",
    "NK": "Spirit",
    "F9": "Frontier",
}

_PNR_LABEL_RE = re.compile(
    r"(?:booking\s*ref(?:erence)?|record\s*locator|confirmation(?:\s*(?:no\.?|number|code))?|pnr)"
    r"\s*[:\-]?\s*(?:[A-Z]{2}\s*/\s*)?([A-Z0-9]{5,8})\b",
    re.IGNORECASE,
)
_PASSENGER_LINE_RE = re.compile(
    r"(?:passenger|name|traveler|traveller)\s*[:\-]\s*(.+?)(?:\s+pnr\b|$)",
    re.IGNORECASE,
)
_LAST_FIRST_RE = re.compile(
    r"\b([A-Z]{2,})/([A-Z]{2,})(?:\s+(?:MR|MS|MRS|MISS|MSTR))?\b"
)
_FLIGHT_LABEL_RE = re.compile(
    r"FLIGHT(?:\s*\(S\))?(?:\s+NO(?:\.|MBER)?)?\s+([A-Z]{2})\s*-?\s*(\d{1,4})\b",
    re.IGNORECASE,
)
_FLIGHT_COMPACT_RE = re.compile(r"\b([A-Z]{2})(\d{3,4})\b")
_DEP_RE = re.compile(r"DEPARTURE:\s*([^,\n(]+)", re.IGNORECASE)
_ARR_RE = re.compile(r"ARRIVAL:\s*([^,\n(]+)", re.IGNORECASE)
_CLASS_RE = re.compile(
    r"\b(PREMIUM\s+ECONOMY|ECONOMY|BUSINESS|FIRST|PREMIUM\s+BUSINESS)\b",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(\d{1,2})\s*([A-Z]{3})[A-Z]*\s*(20\d{2})\b",
    re.IGNORECASE,
)
_DATE_SHORT_RE = re.compile(r"\b(\d{1,2})([A-Z]{3})\b", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_YEAR_RE = re.compile(r"\b(20\d{2})\b")

_NAME_BLOCKLIST = {
    "FLIGHT",
    "BOOKING",
    "TICKET",
    "AIRLINE",
    "GENERAL",
    "SOURCE",
    "CLICK",
    "HAVE",
    "CHECK",
    "DATA",
    "YOUR",
    "NON",
    "STOP",
    "OPERATED",
    "EQUIPMENT",
    "BAGGAGE",
    "ALLOWANCE",
    "RESERVATION",
    "CONFIRMED",
    "DURATION",
    "TERMINAL",
    "AIRLINKERS",
    "TRAVELS",
}


def _pdf_text(raw: bytes) -> str:
    """Pull plain text from a PDF. Empty string on failure or image-only pages."""
    try:
        reader = PdfReader(io.BytesIO(raw))
        parts: list[str] = []
        for page in reader.pages:
            chunk = page.extract_text() or ""
            if chunk.strip():
                parts.append(chunk)
        return "\n".join(parts).strip()
    except Exception as exc:
        logger.info("pdf text extract failed: %s", exc)
        return ""


def sniff_upload(
    raw: bytes, filename: str | None, content_type: str | None
) -> tuple[str, bytes | None, str | None]:
    """Return (text, file_bytes, mime). PDFs become text when extractable."""
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime == "image/jpg":
        mime = "image/jpeg"
    name = (filename or "").lower()
    if not mime or mime == "application/octet-stream":
        if name.endswith(".pdf") or raw.startswith(b"%PDF"):
            mime = "application/pdf"
        elif name.endswith(".png") or raw.startswith(b"\x89PNG"):
            mime = "image/png"
        elif name.endswith((".jpg", ".jpeg")) or raw.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif name.endswith(".webp") or (len(raw) >= 12 and raw[8:12] == b"WEBP"):
            mime = "image/webp"
        elif name.endswith(".gif") or raw.startswith(b"GIF8"):
            mime = "image/gif"
        elif name.endswith((".heic", ".heif")):
            mime = "image/heic"
        else:
            mime = "text/plain"
    if mime == "application/pdf":
        text = _pdf_text(raw)
        if text:
            return text, None, None
        return "", raw, mime
    if mime in _IMAGE_TYPES:
        return "", raw, mime
    try:
        return raw.decode("utf-8"), None, None
    except UnicodeDecodeError:
        if raw.startswith(b"%PDF"):
            text = _pdf_text(raw)
            if text:
                return text, None, None
            return "", raw, "application/pdf"
        return raw[:4000].decode("latin-1", errors="replace"), None, None


def _field(parsed: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = parsed.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _normalize_pnr(value: str) -> str:
    text = value.strip().upper().replace(" ", "")
    prefixed = re.fullmatch(r"[A-Z]{2}/([A-Z0-9]{5,8})", text)
    if prefixed:
        return prefixed.group(1)
    return text


def _title_name(last: str, first: str) -> str:
    return f"{first.title()} {last.title()}"


def _iso_date(day: str, month_token: str, year: str) -> str:
    month = _MONTHS.get(month_token[:3].upper())
    if not month:
        return ""
    return f"{year}-{month}-{int(day):02d}"


def _from_parsed(parsed: dict) -> Extracted | None:
    try:
        raw_pnr = _field(parsed, _PNR_KEYS)
        pnr = _normalize_pnr(raw_pnr) if raw_pnr else ""
        return Extracted(
            passenger_name=_field(parsed, _NAME_KEYS),
            pnr=pnr,
            airline=_field(parsed, _AIRLINE_KEYS),
            flight_number=_field(parsed, _FLIGHT_KEYS),
            date=_field(parsed, _DATE_KEYS),
            route=_field(parsed, _ROUTE_KEYS),
            ticket_class=_field(parsed, _CLASS_KEYS),
        )
    except Exception:
        return None


def _passenger_from_text(text: str) -> str:
    labeled = _PASSENGER_LINE_RE.search(text)
    if labeled:
        raw = labeled.group(1).strip()
        last_first = _LAST_FIRST_RE.search(raw.upper())
        if last_first:
            return _title_name(last_first.group(1), last_first.group(2))
        cleaned = re.sub(r"\s+", " ", raw).strip(" -")
        if cleaned:
            return cleaned.title() if cleaned.isupper() else cleaned
    for match in _LAST_FIRST_RE.finditer(text.upper()):
        last, first = match.group(1), match.group(2)
        if last in _NAME_BLOCKLIST or first in _NAME_BLOCKLIST:
            continue
        return _title_name(last, first)
    return ""


def _pnr_from_text(text: str) -> str:
    match = _PNR_LABEL_RE.search(text)
    if match:
        return match.group(1).upper()
    return ""


def _flight_from_text(text: str) -> tuple[str, str]:
    labeled = _FLIGHT_LABEL_RE.search(text)
    if labeled:
        code, number = labeled.group(1).upper(), labeled.group(2)
        return _AIRLINES.get(code, ""), f"{code} {number}"
    compact = _FLIGHT_COMPACT_RE.search(text)
    if compact:
        code, number = compact.group(1).upper(), compact.group(2)
        if code in _AIRLINES or "FLIGHT" in text.upper():
            return _AIRLINES.get(code, ""), f"{code} {number}"
    return "", ""


def _looks_like_issue_date(text: str, start: int) -> bool:
    prefix = text[max(0, start - 16) : start].upper()
    return bool(re.search(r"\bDATE\s*:\s*$", prefix))


def _date_from_text(text: str) -> str:
    iso = _ISO_DATE_RE.search(text)
    if iso and not _looks_like_issue_date(text, iso.start()):
        return iso.group(1)
    for match in _DATE_RE.finditer(text):
        if _looks_like_issue_date(text, match.start()):
            continue
        return _iso_date(match.group(1), match.group(2), match.group(3))
    year_match = _YEAR_RE.search(text)
    year = year_match.group(1) if year_match else ""
    for match in _DATE_SHORT_RE.finditer(text):
        if _looks_like_issue_date(text, match.start()):
            continue
        if year:
            return _iso_date(match.group(1), match.group(2), year)
    return ""


def _route_from_text(text: str) -> str:
    deps = [re.sub(r"\s+", " ", part).strip(" ,") for part in _DEP_RE.findall(text)]
    arrs = [re.sub(r"\s+", " ", part).strip(" ,") for part in _ARR_RE.findall(text)]
    deps = [part for part in deps if part]
    arrs = [part for part in arrs if part]
    if deps and arrs:
        start = deps[0].title() if deps[0].isupper() else deps[0]
        end = arrs[-1].title() if arrs[-1].isupper() else arrs[-1]
        return f"{start} → {end}"
    return ""


def _class_from_text(text: str) -> str:
    match = _CLASS_RE.search(text)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).title()


def from_ticket_text(document_text: str) -> Extracted | None:
    """Deterministic parse of itinerary / confirmation text. No model call."""
    text = document_text.strip()
    if not text:
        return None
    airline, flight_number = _flight_from_text(text)
    extracted = Extracted(
        passenger_name=_passenger_from_text(text),
        pnr=_pnr_from_text(text),
        airline=airline,
        flight_number=flight_number,
        date=_date_from_text(text),
        route=_route_from_text(text),
        ticket_class=_class_from_text(text),
    )
    if not _usable(extracted):
        return None
    return extracted


def _merge(primary: Extracted | None, secondary: Extracted | None) -> Extracted | None:
    if primary is None:
        return secondary
    if secondary is None:
        return primary
    data = primary.model_dump()
    for key, value in secondary.model_dump().items():
        if not str(data.get(key) or "").strip() and value:
            data[key] = value
    return Extracted(**data)


def _usable(extracted: Extracted | None) -> bool:
    if extracted is None:
        return False
    if extracted.pnr:
        return True
    return bool(extracted.passenger_name and extracted.flight_number)


async def extract_booking(
    document_text: str,
    *,
    file_bytes: bytes | None = None,
    mime_type: str | None = None,
) -> tuple[Extracted | None, bool]:
    """Return (extracted, used_local_fallback). Never returns the demo stub."""
    local = from_ticket_text(document_text)
    if local is not None and local.pnr and local.passenger_name:
        logger.info("extractor used local ticket parse skipped_llm=1")
        return local, True
    user = document_text[:8000].strip()
    if not user:
        user = (
            "Extract the booking fields from the attached ticket."
            if file_bytes
            else "(empty upload)"
        )
    result = await generate_content(
        "EXTRACTOR",
        system=_SYSTEM,
        user=user,
        file_bytes=file_bytes,
        mime_type=mime_type,
        temperature=0,
        max_tokens=2048,
    )
    parsed = result.parsed or parse_json_object(result.text)
    extracted = _from_parsed(parsed) if parsed else None
    merged = _merge(extracted, local)
    if _usable(merged) and result.ok and extracted is not None:
        return merged, False
    if _usable(merged):
        logger.info(
            "extractor used local ticket parse ok=%s error=%s",
            result.ok,
            result.error,
        )
        return merged, True
    logger.info("extractor failed ok=%s error=%s", result.ok, result.error)
    return None, True
