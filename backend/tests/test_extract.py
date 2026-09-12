from app.extract import extract_booking, sniff_upload
from app.llm.provider import reset_providers


def test_sniff_keeps_pdf_bytes() -> None:
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
