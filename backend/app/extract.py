"""Grok booking extraction (PDF text via pypdf). Falls back to canned on failure."""

from __future__ import annotations

import io
import logging

from pypdf import PdfReader

from app.canned import CANNED_EXTRACTED
from app.llm.provider import generate_content, parse_json_object
from app.models import Extracted

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Extract a flight booking from the ticket. Reply with a single JSON "
    "object and nothing else: "
    '{"passenger_name":"","pnr":"","airline":"","flight_number":"","date":"",'
    '"route":"","ticket_class":""}. '
    "pnr is the record locator / confirmation code. Use empty strings when unknown."
)

_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/heic",
    "image/heif",
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


def _field(parsed: dict, key: str) -> str:
    value = parsed.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _from_parsed(parsed: dict) -> Extracted | None:
    try:
        return Extracted(
            passenger_name=_field(parsed, "passenger_name"),
            pnr=_field(parsed, "pnr"),
            airline=_field(parsed, "airline"),
            flight_number=_field(parsed, "flight_number"),
            date=_field(parsed, "date"),
            route=_field(parsed, "route"),
            ticket_class=_field(parsed, "ticket_class"),
        )
    except Exception:
        return None


async def extract_booking(
    document_text: str,
    *,
    file_bytes: bytes | None = None,
    mime_type: str | None = None,
) -> tuple[Extracted, bool]:
    """Return (extracted, used_canned_fallback)."""
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
        max_tokens=1024,
    )
    parsed = result.parsed or parse_json_object(result.text)
    extracted = _from_parsed(parsed) if parsed else None
    if extracted is None or not extracted.pnr:
        logger.info("extractor fallback canned ok=%s error=%s", result.ok, result.error)
        return CANNED_EXTRACTED, True
    return extracted, False
