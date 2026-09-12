from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock

import pytest

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from app.telephony.runtime import (  # noqa: E402
    CallRuntime,
    reset_for_tests,
    start_call,
)
from app.telephony.twiml import END_CONFERENCE_ON_EXIT, browser_twiml, rep_twiml
from app.telephony.twilio_ops import (  # noqa: E402
    add_agent_leg,
    add_browser_leg,
    add_rep_leg,
    hangup_agent,
    unmute_browser,
)


def _conference_el(xml: str) -> ET.Element:
    root = ET.fromstring(xml)
    conference = root.find(".//{*}Conference")
    assert conference is not None, xml
    return conference


def test_end_conference_on_exit_constant_is_false():
    assert END_CONFERENCE_ON_EXIT is False


def test_browser_twiml_muted_and_end_conference_on_exit_false():
    xml = browser_twiml("abc123")
    conference = _conference_el(xml)
    assert conference.text == "cmm-abc123"
    assert conference.attrib.get("muted") == "true"
    assert conference.attrib.get("endConferenceOnExit") == "false"


def test_rep_twiml_has_fee_trigger_and_no_conference():
    xml = rep_twiml(None)
    assert "two hundred dollar cancellation fee" in xml.lower() or "200" in xml
    assert "Conference" not in xml
    assert "$200" in xml or "two hundred dollar" in xml.lower()


def test_add_legs_pass_end_conference_on_exit_false():
    client = MagicMock()
    participants = client.conferences.return_value.participants
    created = MagicMock(call_sid="CA_browser", conference_sid="CF_test")
    participants.create.return_value = created
    client.calls.create.return_value = MagicMock(sid="CA_rep")
    config = MagicMock(
        caller_number="+15551111111",
        rep_number="+15552222222",
    )
    runtime = CallRuntime(session_id="abc123", conference="cmm-abc123")

    add_rep_leg(client, config, runtime, "https://example.test/twilio/status")
    add_browser_leg(client, config, runtime, "https://example.test/twilio/status")

    outbound = client.calls.create.call_args.kwargs
    assert outbound["to"] == "+15552222222"
    assert outbound["from_"] == "+15551111111"
    assert "two hundred dollar" in outbound["twiml"].lower() or "fee" in outbound["twiml"].lower()
    assert "Conference" not in outbound["twiml"]
    assert runtime.rep_call_sid == "CA_rep"

    kwargs = participants.create.call_args.kwargs
    assert kwargs["end_conference_on_exit"] is False
    assert kwargs["muted"] is True
    assert kwargs["to"] == "client:user-abc123"
    assert kwargs["label"] == "browser"


def test_takeover_unmutes_browser_and_does_not_end_conference():
    client = MagicMock()
    runtime = CallRuntime(
        session_id="abc123",
        conference="cmm-abc123",
        agent_call_sid="CA_agent",
    )

    unmute_browser(client, runtime)
    hangup_agent(client, runtime)

    update = client.conferences.return_value.participants.return_value.update
    assert update.call_count >= 1
    for call in update.call_args_list:
        if "end_conference_on_exit" in call.kwargs:
            assert call.kwargs["end_conference_on_exit"] is False
    unmute_kwargs = update.call_args_list[0].kwargs
    assert unmute_kwargs["muted"] is False
    assert unmute_kwargs["end_conference_on_exit"] is False
    client.conferences.return_value.participants.return_value.delete.assert_called()


def test_hangup_agent_noop_without_leg():
    client = MagicMock()
    runtime = CallRuntime(session_id="abc123", conference="cmm-abc123")
    hangup_agent(client, runtime)
    client.conferences.assert_not_called()
    client.calls.assert_not_called()


@pytest.fixture(autouse=True)
def _reset_runtime():
    reset_for_tests()
    yield
    reset_for_tests()


def test_add_agent_leg_end_conference_on_exit_false():
    client = MagicMock()
    participants = client.conferences.return_value.participants
    created = MagicMock(call_sid="CA_agent", conference_sid="CF_test")
    participants.create.return_value = created
    config = MagicMock(
        caller_number="+15551111111",
        agent_number="+15553333333",
        agent_voice_url=MagicMock(return_value="https://example.test/twilio/voice/agent"),
    )
    runtime = CallRuntime(session_id="abc123", conference="cmm-abc123")

    add_agent_leg(client, config, runtime, "https://example.test/twilio/status")

    kwargs = participants.create.call_args.kwargs
    assert kwargs["end_conference_on_exit"] is False
    assert kwargs["label"] == "agent"
    assert kwargs["to"] == "+15553333333"
    assert kwargs["muted"] is False
    assert "early_media" not in kwargs
    assert runtime.agent_call_sid == "CA_agent"


def test_add_rep_leg_places_outbound_call():
    client = MagicMock()
    created = MagicMock(sid="CA_outbound")
    client.calls.create.return_value = created
    config = MagicMock(
        caller_number="+15551111111",
        rep_number="+15552222222",
    )
    runtime = CallRuntime(session_id="abc123", conference="cmm-abc123")

    add_rep_leg(client, config, runtime, "https://example.test/twilio/status")

    client.conferences.assert_not_called()
    kwargs = client.calls.create.call_args.kwargs
    assert kwargs["to"] == "+15552222222"
    assert kwargs["from_"] == "+15551111111"
    assert "Conference" not in kwargs["twiml"]
    assert "cancellation fee" in kwargs["twiml"].lower() or "two hundred" in kwargs["twiml"].lower()
    assert runtime.rep_call_sid == "CA_outbound"


def test_add_rep_leg_inline_twiml_starts_scribe_stream():
    client = MagicMock()
    client.calls.create.return_value = MagicMock(sid="CA_outbound")
    config = MagicMock(
        caller_number="+15551111111",
        rep_number="+15552222222",
        rep_mode="scripted",
        media_stream_url=lambda sid: f"wss://example.test/twilio/media/{sid}",
        rep_voice_url=lambda _sid: None,
    )
    runtime = CallRuntime(session_id="abc123", conference="cmm-abc123")

    add_rep_leg(client, config, runtime, None)

    kwargs = client.calls.create.call_args.kwargs
    assert "wss://example.test/twilio/media/abc123" in kwargs["twiml"]
    assert 'track="both_tracks"' in kwargs["twiml"]


def test_add_agent_leg_requires_number():
    client = MagicMock()
    config = MagicMock(caller_number="+15551111111", agent_number="")
    runtime = CallRuntime(session_id="abc123", conference="cmm-abc123")
    with pytest.raises(RuntimeError, match="TWILIO_AGENT_NUMBER"):
        add_agent_leg(client, config, runtime, None)


def test_start_call_conference_name():
    runtime = start_call("deadbeef")
    assert runtime.conference == "cmm-deadbeef"
