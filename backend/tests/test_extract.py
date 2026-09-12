from app.extract import extract_booking
from app.llm.provider import reset_providers


async def test_extract_falls_back_when_extractor_unconfigured(monkeypatch) -> None:
    await reset_providers()
    monkeypatch.delenv("EXTRACTOR_BASE_URL", raising=False)
    monkeypatch.delenv("EXTRACTOR_MODEL", raising=False)
    extracted, fallback = await extract_booking("Passenger: Alex Chen PNR ABC123")
    assert fallback is True
    assert extracted.pnr == "ABC123"
