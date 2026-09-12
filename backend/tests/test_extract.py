from app.canned import CANNED_EXTRACTED, canned_plan
from app.extract import extract_booking, from_ticket_text, sniff_upload
from app.llm.provider import reset_providers
from app.models import Extracted


def _pdf_with_text(payload: str) -> bytes:
    """Minimal one-page PDF whose content stream includes `payload` as a Tj string."""
    stream = f"BT /F1 12 Tf 50 100 Td ({payload}) Tj ET".encode("latin-1")
    objs = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        (
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
            b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
        ),
        (
            f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
            + stream
            + b"\nendstream\nendobj\n"
        ),
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    out = bytearray(b"%PDF-1.1\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(out)


def test_sniff_extracts_text_from_pdf() -> None:
    raw = _pdf_with_text("Passenger: Alex Chen PNR ABC123")
    text, file_bytes, mime = sniff_upload(raw, "ticket.pdf", "application/pdf")
    assert "ABC123" in text
    assert file_bytes is None
    assert mime is None


def test_sniff_keeps_pdf_bytes_when_no_text() -> None:
    raw = b"%PDF-1.4 fake ticket"
    text, file_bytes, mime = sniff_upload(raw, "ticket.pdf", "application/pdf")
    assert text == ""
    assert file_bytes == raw
    assert mime == "application/pdf"


def test_sniff_keeps_png_bytes() -> None:
    raw = b"\x89PNG\r\n\x1a\nrest"
    text, file_bytes, mime = sniff_upload(raw, "pass.png", "image/png")
    assert text == ""
    assert file_bytes == raw
    assert mime == "image/png"


def test_sniff_decodes_plain_text() -> None:
    text, file_bytes, mime = sniff_upload(
        b"Passenger: Alex Chen PNR ABC123", "note.txt", "text/plain"
    )
    assert "ABC123" in text
    assert file_bytes is None
    assert mime is None


async def test_extract_uses_local_parse_when_extractor_unconfigured(monkeypatch) -> None:
    await reset_providers()
    monkeypatch.delenv("EXTRACTOR_BASE_URL", raising=False)
    monkeypatch.delenv("EXTRACTOR_MODEL", raising=False)
    extracted, fallback = await extract_booking("Passenger: Priya Shah PNR ZX9QWE")
    assert fallback is True
    assert extracted is not None
    assert extracted.pnr == "ZX9QWE"
    assert extracted.passenger_name == "Priya Shah"
    assert extracted.pnr != CANNED_EXTRACTED.pnr


def test_from_ticket_text_reads_amadeus_itinerary() -> None:
    text = """
TRAVEL SUMMARY
SMITH/JANE MS
DATE DEP TIME FROM TO FLIGHT NO TERMINAL AIRLINE NAME
17AUG 1905 DELHI DEL TOKYO HND JL030 3 JAPAN AIRLINES
BOOKING REF: 8H2FED
DATE: 14 AUGUST 2026
SMITH/JANE MS
FLIGHT JL 030 - JAPAN AIRLINES MON 17 AUGUST 2026
DEPARTURE: DELHI, DL (INDIRA GANDHI INTL), TERMINAL 3 17 AUG 19:05
ARRIVAL: TOKYO, JP (TOKYO INTL HANEDA), TERMINAL 3 18 AUG 06:45
FLIGHT BOOKING REF: JL/8H2FED
RESERVATION CONFIRMED, ECONOMY (M)
DEPARTURE: TOKYO, JP
ARRIVAL: NEW YORK, NY (JOHN F KENNEDY INTL)
DEPARTURE: NEW YORK, NY
ARRIVAL: PITTSBURGH, PA (INTERNATIONAL)
"""
    extracted = from_ticket_text(text)
    assert extracted is not None
    assert extracted.pnr == "8H2FED"
    assert extracted.passenger_name == "Jane Smith"
    assert extracted.airline == "Japan Airlines"
    assert extracted.flight_number == "JL 030"
    assert extracted.date == "2026-08-17"
    assert extracted.ticket_class == "Economy"
    assert extracted.route.startswith("Delhi")
    assert "Pittsburgh" in extracted.route


def test_canned_plan_uses_extracted_passenger() -> None:
    extracted = Extracted(
        passenger_name="Jane Smith",
        pnr="8H2FED",
        airline="Japan Airlines",
        flight_number="JL 030",
        date="2026-08-17",
        route="Delhi → Pittsburgh",
        ticket_class="Economy",
    )
    plan = canned_plan("cancel this flight", extracted)
    assert "Jane Smith" in plan.opening_script
    assert "8H2FED" in plan.opening_script
    assert "Alex Chen" not in plan.opening_script
    assert plan.target_name == "Japan Airlines Reservations"


async def test_extract_returns_none_when_empty_and_unconfigured(monkeypatch) -> None:
    await reset_providers()
    monkeypatch.delenv("EXTRACTOR_BASE_URL", raising=False)
    monkeypatch.delenv("EXTRACTOR_MODEL", raising=False)
    extracted, fallback = await extract_booking("")
    assert fallback is True
    assert extracted is None
