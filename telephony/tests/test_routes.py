from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402
from app.models import SessionState  # noqa: E402
from app.store import set_state  # noqa: E402
from app.telephony.runtime import reset_for_tests, start_call  # noqa: E402


@pytest.fixture
def client():
    reset_for_tests()
    yield TestClient(app)
    reset_for_tests()


def _approve_session(client: TestClient) -> str:
    session_id = client.post("/api/session").json()["session_id"]
    client.post(
        f"/api/session/{session_id}/document",
        files={"file": ("booking.pdf", b"fake", "application/pdf")},
    )
    client.post(f"/api/session/{session_id}/plan", json={"goal": "cancel this flight"})
    client.post(f"/api/session/{session_id}/approve")
    return session_id


@patch("app.telephony.router.load_config")
def test_voice_token_503_without_api_keys(load_config: MagicMock, client: TestClient):
    config = MagicMock()
    config.token_ready = False
    config.missing_token.return_value = ["TWILIO_API_KEY"]
    load_config.return_value = config
    session_id = client.post("/api/session").json()["session_id"]
    response = client.get(f"/api/session/{session_id}/voice-token")
    assert response.status_code == 503
    assert "TWILIO_API_KEY" in response.json()["detail"]


def test_dial_409_before_approve(client: TestClient):
    session_id = client.post("/api/session").json()["session_id"]
    response = client.post(f"/api/session/{session_id}/dial")
    assert response.status_code == 409


@patch("app.telephony.router.load_config")
def test_dial_503_without_numbers(load_config: MagicMock, client: TestClient):
    config = MagicMock()
    config.dial_ready = False
    config.missing_dial.return_value = ["TWILIO_CALLER_NUMBER"]
    load_config.return_value = config
    session_id = _approve_session(client)
    response = client.post(f"/api/session/{session_id}/dial")
    assert response.status_code == 503
    assert "TWILIO_CALLER_NUMBER" in response.json()["detail"]


@patch("app.telephony.router.load_config")
def test_browser_twiml_route_muted(load_config: MagicMock, client: TestClient):
    config = MagicMock()
    config.status_url.return_value = None
    load_config.return_value = config
    session_id = client.post("/api/session").json()["session_id"]
    response = client.post(f"/twilio/voice/browser?session_id={session_id}")
    assert response.status_code == 200
    body = response.text
    assert "muted" in body
    assert "endConferenceOnExit" in body
    assert "false" in body
    assert f"cmm-{session_id}" in body


def test_rep_twiml_route_fee_trigger(client: TestClient):
    response = client.post("/twilio/voice/rep")
    assert response.status_code == 200
    assert "fee" in response.text.lower()
    assert "Conference" not in response.text


@patch("app.telephony.router.rest_client")
@patch("app.telephony.router.load_config")
def test_dial_then_takeover_unmutes(
    load_config: MagicMock, rest_client: MagicMock, client: TestClient
):
    config = MagicMock()
    config.dial_ready = True
    config.rest_ready = True
    config.agent_leg_ready = False
    config.caller_number = "+15551111111"
    config.rep_number = "+15552222222"
    config.agent_number = ""
    config.status_url.return_value = "https://example.test/twilio/status"
    load_config.return_value = config

    twilio = MagicMock()
    rest_client.return_value = twilio
    twilio.conferences.return_value.participants.create.return_value = MagicMock(
        call_sid="CA_rep",
        conference_sid="CF1",
    )

    session_id = _approve_session(client)
    # approve() already invokes dial when Twilio is configured
    session = client.get(f"/api/session/{session_id}")
    assert session.status_code == 200
    assert session.json()["state"] == "DIALING"

    set_state(session_id, SessionState.IN_CALL)
    takeover = client.post(f"/api/session/{session_id}/takeover")
    assert takeover.status_code == 200
    assert takeover.json()["state"] == "HUMAN_CONTROL"
    assert "leg_c_unmuted_ts" in takeover.json()

    update = twilio.conferences.return_value.participants.return_value.update
    assert update.call_args_list[0].kwargs["muted"] is False
    assert update.call_args_list[0].kwargs["end_conference_on_exit"] is False


def test_status_dialing_to_in_call(client: TestClient):
    session_id = _approve_session(client)
    set_state(session_id, SessionState.DIALING)
    start_call(session_id)
    response = client.post(
        f"/twilio/status?session_id={session_id}",
        data={
            "StatusCallbackEvent": "participant-join",
            "ParticipantLabel": "rep",
            "CallSid": "CA_rep",
            "FriendlyName": f"cmm-{session_id}",
        },
    )
    assert response.status_code == 200
    blob = client.get(f"/api/session/{session_id}")
    assert blob.json()["state"] == "IN_CALL"


def test_status_does_not_end_on_single_leg_completed(client: TestClient):
    session_id = _approve_session(client)
    set_state(session_id, SessionState.IN_CALL)
    start_call(session_id)
    response = client.post(
        f"/twilio/status?session_id={session_id}",
        data={
            "CallStatus": "completed",
            "ParticipantLabel": "browser",
            "CallSid": "CA_browser",
        },
    )
    assert response.status_code == 200
    blob = client.get(f"/api/session/{session_id}")
    assert blob.json()["state"] == "IN_CALL"


def test_status_conference_end_goes_ended(client: TestClient):
    session_id = _approve_session(client)
    set_state(session_id, SessionState.HUMAN_CONTROL)
    start_call(session_id)
    response = client.post(
        f"/twilio/status?session_id={session_id}",
        data={
            "StatusCallbackEvent": "conference-end",
            "FriendlyName": f"cmm-{session_id}",
        },
    )
    assert response.status_code == 200
    blob = client.get(f"/api/session/{session_id}")
    assert blob.json()["state"] == "ENDED"


def test_status_does_not_regress_human_control_to_in_call(client: TestClient):
    session_id = _approve_session(client)
    set_state(session_id, SessionState.HUMAN_CONTROL)
    start_call(session_id)
    response = client.post(
        f"/twilio/status?session_id={session_id}",
        data={
            "StatusCallbackEvent": "participant-join",
            "ParticipantLabel": "rep",
            "CallSid": "CA_rep",
        },
    )
    assert response.status_code == 200
    blob = client.get(f"/api/session/{session_id}")
    assert blob.json()["state"] == "HUMAN_CONTROL"
