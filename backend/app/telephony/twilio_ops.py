from __future__ import annotations

import logging

from twilio.base.exceptions import TwilioRestException
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.rest import Client

from app.telephony.config import TwilioConfig
from app.telephony.runtime import CallRuntime, client_identity
from app.telephony.twiml import END_CONFERENCE_ON_EXIT, conference_join_twiml, rep_twiml

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


def _call_status_kwargs(status_url: str | None) -> dict:
    if not status_url:
        return {}
    return {
        "status_callback": status_url,
        "status_callback_event": STATUS_EVENTS,
    }


def _record_call_sid(record) -> str | None:
    for attr in ("call_sid", "sid"):
        value = getattr(record, attr, None)
        if isinstance(value, str) and value:
            return value
    return None


def _maybe_set_conference_sid(runtime: CallRuntime, record) -> None:
    value = getattr(record, "conference_sid", None)
    if isinstance(value, str) and value:
        runtime.conference_sid = value


def _trial_blocks_participants(exc: Exception) -> bool:
    if not isinstance(exc, TwilioRestException):
        return False
    if exc.code in {20003, 10002}:
        return True
    return "trial account" in str(exc).lower()


def _add_conference_leg(
    client: Client,
    config: TwilioConfig,
    runtime: CallRuntime,
    *,
    to: str,
    label: str,
    muted: bool,
    status_url: str | None,
    voice_url: str | None = None,
):
    """Mix `to` into the conference. Trial accounts reject Participants REST."""
    create_kwargs = {
        "from_": config.caller_number,
        "to": to,
        "label": label,
        "beep": False,
        "muted": muted,
        "start_conference_on_enter": True,
        "end_conference_on_exit": END_CONFERENCE_ON_EXIT,
        **_status_kwargs(status_url),
    }
    try:
        return client.conferences(runtime.conference).participants.create(
            **create_kwargs
        )
    except Exception as exc:
        if not _trial_blocks_participants(exc):
            raise
        logger.warning(
            "participants.create blocked (%s); falling back to Calls + Dial Conference label=%s",
            getattr(exc, "code", exc),
            label,
        )

    call_kwargs = _call_status_kwargs(status_url)
    if voice_url:
        return client.calls.create(
            to=to,
            from_=config.caller_number,
            url=voice_url,
            **call_kwargs,
        )
    return client.calls.create(
        to=to,
        from_=config.caller_number,
        twiml=conference_join_twiml(
            runtime.session_id,
            label=label,
            muted=muted,
            status_url=status_url,
        ),
        **call_kwargs,
    )


def _public_http_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return None


def _media_stream_url(config: TwilioConfig, session_id: str) -> str | None:
    getter = getattr(config, "media_stream_url", None)
    if not callable(getter):
        return None
    value = getter(session_id)
    if isinstance(value, str) and value.startswith(("ws://", "wss://")):
        return value
    return None


def _stream_track(config: TwilioConfig) -> str:
    return "both_tracks"


def start_media_stream(client: Client, config: TwilioConfig, runtime: CallRuntime) -> None:
    """REST fallback if TwiML <Start><Stream> is ignored (common on trial)."""
    url = _media_stream_url(config, runtime.session_id)
    call_sid = runtime.rep_call_sid
    if not url or not call_sid:
        return
    try:
        client.calls(call_sid).streams.create(url=url, track="both_tracks")
        logger.info(
            "media stream REST session_id=%s call_sid=%s url=%s",
            runtime.session_id,
            call_sid,
            url,
        )
    except Exception as exc:
        logger.warning(
            "media stream REST failed session_id=%s err=%s",
            runtime.session_id,
            exc,
        )


def add_rep_leg(
    client: Client,
    config: TwilioConfig,
    runtime: CallRuntime,
    status_url: str | None,
):
    """Place a PSTN outbound call. Trial accounts reject inline Twiml + extra params."""
    from app.store import get_session_or_none

    session = get_session_or_none(runtime.session_id)
    getter = getattr(config, "rep_voice_url", None)
    url = _public_http_url(getter(runtime.session_id) if callable(getter) else None)

    attempts: list[dict] = []
    if url:
        attempts.append(
            {"to": config.rep_number, "from_": config.caller_number, "url": url}
        )
    attempts.append(
        {
            "to": config.rep_number,
            "from_": config.caller_number,
            "twiml": rep_twiml(
                session,
                stream_url=_media_stream_url(config, runtime.session_id),
                session_id=runtime.session_id,
                stream_track=_stream_track(config),
            ),
        }
    )

    last_exc: Exception | None = None
    call = None
    for kwargs in attempts:
        try:
            call = client.calls.create(**kwargs)
            logger.info(
                "outbound rep call session_id=%s sid=%s to=%s via=%s",
                runtime.session_id,
                _record_call_sid(call),
                config.rep_number,
                "url" if "url" in kwargs else "twiml",
            )
            break
        except TwilioRestException as exc:
            last_exc = exc
            logger.warning(
                "outbound call rejected session_id=%s via=%s msg=%s",
                runtime.session_id,
                "url" if "url" in kwargs else "twiml",
                exc.msg,
            )
    if call is None:
        raise last_exc or RuntimeError("twilio outbound call failed")

    runtime.rep_call_sid = _record_call_sid(call)
    start_media_stream(client, config, runtime)
    return call


def add_browser_leg(
    client: Client,
    config: TwilioConfig,
    runtime: CallRuntime,
    status_url: str | None,
):
    participant = _add_conference_leg(
        client,
        config,
        runtime,
        to=f"client:{client_identity(runtime.session_id)}",
        label="browser",
        muted=True,
        status_url=status_url,
    )
    runtime.browser_call_sid = _record_call_sid(participant)
    _maybe_set_conference_sid(runtime, participant)
    return participant


def add_agent_leg(
    client: Client,
    config: TwilioConfig,
    runtime: CallRuntime,
    status_url: str | None,
):
    """Add Leg B as a conference participant whose Voice URL returns register_call TwiML.

    TWILIO_AGENT_NUMBER must be a Twilio number whose Voice webhook is
    {PUBLIC_BASE_URL}/twilio/voice/agent. participants.create already mixes the
    answered call into the conference — the webhook must NOT Dial the conference
    again (same pattern as the scripted rep).
    """
    if not config.agent_number:
        raise RuntimeError("TWILIO_AGENT_NUMBER required to dial agent leg")

    participant = _add_conference_leg(
        client,
        config,
        runtime,
        to=config.agent_number,
        label="agent",
        muted=False,
        status_url=status_url,
        voice_url=config.agent_voice_url(runtime.session_id),
    )
    runtime.agent_call_sid = _record_call_sid(participant)
    _maybe_set_conference_sid(runtime, participant)
    logger.info(
        "agent leg session_id=%s call_sid=%s to=%s",
        runtime.session_id,
        runtime.agent_call_sid,
        config.agent_number,
    )
    return participant


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
