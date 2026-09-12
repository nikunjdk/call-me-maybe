"""Failure paths first. Real localhost OpenAI-shaped server, not a mocked client."""

from app.llm.provider import reset_providers
from app.policy.gate import classify
from app.policy.hard_net import hard_check

from tests.conftest import set_mode

BENIGN = "Your confirmation number is ABC123. What would you like to do today?"
FEE = "There is a $200 change fee to move this flight."


def test_hard_net_silent_on_benign() -> None:
    assert hard_check(BENIGN) is None


def test_hard_net_forces_escalate_on_fee() -> None:
    hit = hard_check(FEE)
    assert hit is not None
    assert hit.trigger == "money"


def test_hard_net_cannot_return_allow() -> None:
    assert not hasattr(hard_check(BENIGN), "verdict")
    assert hard_check(BENIGN) is None
    assert hard_check(FEE) is not None


async def test_unparseable_prose_escalates_degraded(fake_llm) -> None:
    set_mode(fake_llm["origin"], "prose")
    verdict = await classify(BENIGN)
    assert verdict.verdict == "ESCALATE"
    assert verdict.degraded is True
    assert "unparseable" in " ".join(verdict.notes).lower() or "unparseable" in verdict.reason


async def test_http_503_escalates_degraded(fake_llm) -> None:
    set_mode(fake_llm["origin"], "503")
    verdict = await classify(BENIGN)
    assert verdict.verdict == "ESCALATE"
    assert verdict.degraded is True
    assert "503" in verdict.reason or any("503" in n for n in verdict.notes)


async def test_timeout_escalates_degraded(fake_llm, monkeypatch) -> None:
    monkeypatch.setenv("TIER1_TIMEOUT", "0.2")
    await reset_providers()
    set_mode(fake_llm["origin"], "slow")
    verdict = await classify(BENIGN)
    assert verdict.verdict == "ESCALATE"
    assert verdict.degraded is True


async def test_missing_config_escalates_degraded(monkeypatch) -> None:
    await reset_providers()
    monkeypatch.delenv("TIER1_BASE_URL", raising=False)
    monkeypatch.delenv("TIER1_MODEL", raising=False)
    verdict = await classify(BENIGN)
    assert verdict.verdict == "ESCALATE"
    assert verdict.degraded is True


async def test_fenced_json_parses(fake_llm) -> None:
    set_mode(fake_llm["origin"], "fenced")
    verdict = await classify(BENIGN)
    assert verdict.verdict == "ALLOW"
    assert verdict.degraded is False
    assert verdict.tier == 1


async def test_hard_net_overrides_wrong_allow(fake_llm) -> None:
    set_mode(fake_llm["origin"], "allow_money")
    verdict = await classify(FEE)
    assert verdict.verdict == "ESCALATE"
    assert verdict.tier == 0
    assert verdict.trigger == "money"
    assert any("overrode" in n for n in verdict.notes)


async def test_hard_net_stays_silent_on_benign(fake_llm) -> None:
    set_mode(fake_llm["origin"], "valid")
    verdict = await classify(BENIGN)
    assert verdict.verdict == "ALLOW"
    assert verdict.tier == 1
    assert verdict.trigger == "none"
    assert not any("hard net" in n for n in verdict.notes)


async def test_uncertain_band_reaches_tier2(fake_llm) -> None:
    set_mode(fake_llm["origin"], "low_confidence", model="fake-tier1")
    set_mode(fake_llm["origin"], "escalate_high", model="fake-tier2")
    verdict = await classify(BENIGN)
    assert verdict.tier == 2
    assert verdict.verdict == "ESCALATE"
    assert verdict.degraded is False
    assert verdict.tier2_latency_ms is not None
    assert any("uncertain" in n for n in verdict.notes)
