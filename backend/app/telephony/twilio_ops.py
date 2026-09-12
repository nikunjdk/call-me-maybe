from __future__ import annotations

import logging

from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.rest import Client

from app.telephony.config import TwilioConfig
from app.telephony.runtime import CallRuntime, client_identity
from app.telephony.twiml import END_CONFERENCE_ON_EXIT

logger = logging.getLogger(__name__)

STATUS_EVENTS = ["initiated", "ringing", "answered", "completed"]
CONFERENCE_EVENTS = ["start", "end", "join", "leave"]


def rest_client(config: TwilioConfig) -> Client:
    return Client(config.account_sid, config.auth_token)


def mint_voice_token(config: TwilioConfig, session_id: str) -> tuple[str, str]:
    identity = client_identity(session_id)
    token = AccessToken(
        config.account_sid,
        config.api_key,
        config.api_secret,
        identity=identity,
        ttl=3600,
    )
    token.add_grant(
        VoiceGrant(
            outgoing_application_sid=config.twiml_app_sid,
            incoming_allow=True,
        )
    )
    jwt = token.to_jwt()
    if isinstance(jwt, bytes):
        jwt = jwt.decode("utf-8")
    return jwt, identity


def _status_kwargs(status_url: str | None) -> dict:
    if not status_url:
        return {}
    return {
        "status_callback": status_url,
        "status_callback_event": STATUS_EVENTS,
        "conference_status_callback": status_url,
        "conference_status_callback_event": CONFERENCE_EVENTS,
    }


def add_rep_leg(
    client: Client,
    config: TwilioConfig,
    runtime: CallRuntime,
    status_url: str | None,
):
    participant = client.conferences(runtime.conference).participants.create(
        from_=config.caller_number,
        to=config.rep_number,
        label="rep",
        beep=False,
        muted=False,
        start_conference_on_enter=True,
        end_conference_on_exit=END_CONFERENCE_ON_EXIT,
        early_media=True,
        **_status_kwargs(status_url),
    )
    runtime.rep_call_sid = getattr(participant, "call_sid", None)
    runtime.conference_sid = getattr(participant, "conference_sid", None)
    return participant


def add_browser_leg(
    client: Client,
    config: TwilioConfig,
    runtime: CallRuntime,
    status_url: str | None,
):
    participant = client.conferences(runtime.conference).participants.create(
        from_=config.caller_number,
        to=f"client:{client_identity(runtime.session_id)}",
        label="browser",
        beep=False,
        muted=True,
        start_conference_on_enter=True,
        end_conference_on_exit=END_CONFERENCE_ON_EXIT,
        early_media=True,
        **_status_kwargs(status_url),
    )
    runtime.browser_call_sid = getattr(participant, "call_sid", None)
    if getattr(participant, "conference_sid", None):
        runtime.conference_sid = participant.conference_sid
    return participant


def add_agent_leg(
    client: Client,
    config: TwilioConfig,
    runtime: CallRuntime,
    status_url: str | None,
):
    """Dial Leg B so Twilio hits /twilio/voice/agent → ElevenLabs register_call TwiML.

    Preferred: participants.create to TWILIO_AGENT_NUMBER (Voice URL must point at
    {PUBLIC_BASE_URL}/twilio/voice/agent). Fallback: outbound Calls.create with
    url=agent webhook when no third number is configured.
    """
    agent_url = config.agent_voice_url(runtime.session_id)
    if not agent_url:
        raise RuntimeError("PUBLIC_BASE_URL required to dial agent leg")

    if config.agent_number:
        participant = client.conferences(runtime.conference).participants.create(
            from_=config.caller_number,
            to=config.agent_number,
            label="agent",
            beep=False,
            muted=False,
            start_conference_on_enter=True,
            end_conference_on_exit=END_CONFERENCE_ON_EXIT,
            early_media=True,
            **_status_kwargs(status_url),
        )
        runtime.agent_call_sid = getattr(participant, "call_sid", None)
        if getattr(participant, "conference_sid", None):
            runtime.conference_sid = participant.conference_sid
        logger.info(
            "agent leg via participant session_id=%s call_sid=%s to=%s",
            runtime.session_id,
            runtime.agent_call_sid,
            config.agent_number,
        )
        return participant

    # Fallback: explicit webhook URL so register_call TwiML is fetched.
    to_number = config.caller_number
    status_kwargs = {}
    if status_url:
        status_kwargs = {
            "status_callback": status_url,
            "status_callback_event": STATUS_EVENTS,
        }
    call = client.calls.create(
        from_=config.caller_number,
        to=to_number,
        url=agent_url,
        method="POST",
        **status_kwargs,
    )
    runtime.agent_call_sid = getattr(call, "sid", None)
    logger.info(
        "agent leg via calls.create fallback session_id=%s call_sid=%s url=%s",
        runtime.session_id,
        runtime.agent_call_sid,
        agent_url,
    )
    return call


def unmute_browser(client: Client, runtime: CallRuntime) -> None:
    client.conferences(runtime.conference).participants("browser").update(
        muted=False,
        end_conference_on_exit=END_CONFERENCE_ON_EXIT,
    )


def hangup_agent(client: Client, runtime: CallRuntime) -> None:
    """Drop Leg B without ending the conference. No-op until B joins."""
    if not runtime.agent_call_sid:
        logger.info("no agent leg to terminate session_id=%s", runtime.session_id)
        return
    try:
        client.conferences(runtime.conference).participants("agent").update(
            end_conference_on_exit=END_CONFERENCE_ON_EXIT,
        )
        client.conferences(runtime.conference).participants("agent").delete()
    except Exception:
        logger.warning(
            "agent participant delete failed; completing call %s",
            runtime.agent_call_sid,
            exc_info=True,
        )
        client.calls(runtime.agent_call_sid).update(status="completed")
    runtime.agent_call_sid = None
