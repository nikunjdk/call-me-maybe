from app.llm.provider import chat, parse_json_object, reset_providers

from tests.conftest import set_mode

BENIGN = "Your confirmation number is ABC123. What would you like to do today?"


def test_parse_fenced_json() -> None:
    text = '```json\n{"verdict":"ALLOW","trigger":"none","reason":"ok","confidence":0.91}\n```'
    parsed = parse_json_object(text)
    assert parsed is not None
    assert parsed["verdict"] == "ALLOW"


def test_parse_leading_sentence() -> None:
    text = 'Sure, here is the object:\n{"verdict":"ESCALATE","trigger":"money","reason":"fee","confidence":0.8}'
    parsed = parse_json_object(text)
    assert parsed is not None
    assert parsed["trigger"] == "money"


def test_parse_prose_returns_none() -> None:
    assert parse_json_object("I cannot help with that in JSON.") is None


async def test_chat_never_raises_on_missing_config(monkeypatch) -> None:
    await reset_providers()
    monkeypatch.delenv("TIER1_BASE_URL", raising=False)
    monkeypatch.delenv("TIER1_MODEL", raising=False)
    result = await chat("TIER1", [{"role": "user", "content": "hi"}])
    assert result.ok is False
    assert result.error
    assert "missing" in result.error


async def test_chat_http_503(fake_llm) -> None:
    set_mode(fake_llm["origin"], "503")
    result = await chat("TIER1", [{"role": "user", "content": BENIGN}])
    assert result.ok is False
    assert result.error == "http 503"
    assert result.provider_label == "K2-0.9B · fake"


async def test_chat_timeout(fake_llm, monkeypatch) -> None:
    monkeypatch.setenv("TIER1_TIMEOUT", "0.2")
    await reset_providers()
    set_mode(fake_llm["origin"], "slow")
    result = await chat("TIER1", [{"role": "user", "content": BENIGN}])
    assert result.ok is False
    assert result.error


async def test_chat_fenced_json_over_network(fake_llm) -> None:
    set_mode(fake_llm["origin"], "fenced")
    result = await chat("TIER1", [{"role": "user", "content": BENIGN}])
    assert result.ok is True
    assert result.parsed is not None
    assert result.parsed["verdict"] == "ALLOW"
    assert result.provider_label == "K2-0.9B · fake"
