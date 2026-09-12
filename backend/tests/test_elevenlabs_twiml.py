from app.telephony.config import TwilioConfig
from app.telephony.elevenlabs_twilio import conversation_id_from_twiml
from app.telephony.twiml import rep_twiml


def test_conversation_id_from_stream_url() -> None:
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response><Connect>"
        '<Stream url="wss://api.elevenlabs.io/v1/convai/conversation?agent_id=x&amp;conversation_id=conv_abc123"/>'
        "</Connect></Response>"
    )
    assert conversation_id_from_twiml(twiml) == "conv_abc123"


def test_conversation_id_from_bare_token() -> None:
    assert conversation_id_from_twiml("sid=conv_zz99 extra") == "conv_zz99"


def test_rep_twiml_starts_scribe_media_stream() -> None:
    xml = rep_twiml(
        None,
        stream_url="wss://example.test/twilio/media/abc",
        session_id="abc",
    )
    assert "wss://example.test/twilio/media/abc" in xml
    assert 'track="both_tracks"' in xml
    assert 'name="session_id"' in xml
    assert "Conference" not in xml


def test_media_stream_url_rewrites_https_to_wss() -> None:
    config = TwilioConfig(
        account_sid="",
        auth_token="",
        api_key="",
        api_secret="",
        twiml_app_sid="",
        caller_number="",
        sim_rep_number="",
        live_rep_number="",
        agent_number="",
        rep_mode="scripted",
        public_base_url="https://demo.example",
        validate_signature=False,
    )
    assert config.media_stream_url("abc") == "wss://demo.example/twilio/media/abc"
