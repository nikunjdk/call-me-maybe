from app.extract import extract_booking, sniff_upload
from app.llm.provider import reset_providers


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


async def test_extract_falls_back_when_extractor_unconfigured(monkeypatch) -> None:
    await reset_providers()
    monkeypatch.delenv("EXTRACTOR_BASE_URL", raising=False)
    monkeypatch.delenv("EXTRACTOR_MODEL", raising=False)
    extracted, fallback = await extract_booking("Passenger: Alex Chen PNR ABC123")
    assert fallback is True
    assert extracted.pnr == "ABC123"
