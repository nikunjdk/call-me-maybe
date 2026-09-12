from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Request, WebSocket
from fastapi.responses import Response

from app.agent.live_turns import start_live_ingest, stop_live_ingest
from app.events import emit_event, emit_state
from app.models import SessionState
from app.store import get_session, get_session_or_none, set_state, set_summary, set_timestamps
from app.summarize import generate_summary
from app.telephony.config import load_config
from app.telephony.runtime import (
    get_active,
    get_runtime,
    remember_call_sid,
    session_id_from_conference,
    session_id_from_identity,
    start_call,
)
from app.telephony.elevenlabs_twilio import conversation_id_from_twiml, register_agent_call_twiml
from app.telephony.media import handle_twilio_media
from app.telephony.twilio_ops import (
    add_agent_leg,
    add_browser_leg,
    add_rep_leg,
    hangup_agent,
    mint_voice_token,
    rest_client,
    unmute_browser,
)
from app.telephony.twiml import browser_twiml, rep_twiml
from twilio.twiml.voice_response import VoiceResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telephony"])

_ENDED_STATES = {SessionState.ENDED, SessionState.SUMMARIZED}


def _xml(body: str) -> Response:
    return Response(content=body, media_type="application/xml")


def _form_get(form: dict, *keys: str) -> str:
    for key in keys:
        value = form.get(key)
        if value:
            return str(value)
    return ""


def resolve_session_id(form: dict, query_session_id: str | None) -> str | None:
    if query_session_id:
        return query_session_id
    from_form = _form_get(form, "session_id", "SessionId")
    if from_form:
        return from_form
    conference = session_id_from_conference(
        _form_get(form, "FriendlyName", "ConferenceName")
    )
    if conference:
        return conference
    identity = session_id_from_identity(
        _form_get(form, "From", "To", "Caller", "Called")
    )
    if identity:
        return identity
    active = get_active()
    if active:
        return active.session_id
    return None


def _persist_timestamps(session_id: str, runtime) -> None:
    if runtime is None:
        return
    data = runtime.timestamp_data()
    set_timestamps(
        session_id,
        call_started_ts=data.get("call_started_ts"),
        human_unmuted_ts=data.get("leg_c_unmuted_ts"),
        call_ended_ts=data.get("call_ended_ts"),
    )


def _is_rep_live(event: str, label: str) -> bool:
    if event in {"conference-start", "start"}:
        return True
    if event in {"answered", "in-progress"} and label != "browser":
        return True
    if event in {"join", "participant-join"} and label in {"", "rep"}:
        return True
    return False


@router.get("/api/session/{session_id}/voice-token")
async def voice_token(session_id: str) -> dict[str, str]:
    get_session(session_id)
    config = load_config()
    if not config.token_ready:
        raise HTTPException(
            status_code=503,
            detail=(
                "twilio voice token not configured: missing "
                + ", ".join(config.missing_token())
            ),
        )
    token, identity = mint_voice_token(config, session_id)
    return {"token": token, "identity": identity}


@router.post("/api/session/{session_id}/dial")
async def dial(session_id: str) -> dict:
    session = get_session(session_id)
    if session.state != SessionState.PLAN_APPROVED:
        raise HTTPException(
            status_code=409,
            detail=(
                f"illegal transition: state is {session.state.value}, "
                "expected PLAN_APPROVED"
            ),
        )
    config = load_config()
    if not config.dial_ready:
        raise HTTPException(
            status_code=503,
            detail=(
                "twilio dial not configured: missing "
                + ", ".join(config.missing_dial())
            ),
        )

    runtime = start_call(session_id)
    session = set_state(session_id, SessionState.DIALING)
    await emit_state(session_id, session.state)

    client = rest_client(config)
    status_url = config.status_url(session_id)
    try:
        add_rep_leg(client, config, runtime, status_url)
    except Exception as exc:
        logger.exception("rep leg failed session_id=%s", session_id)
        set_state(session_id, SessionState.PLAN_APPROVED)
        await emit_state(session_id, SessionState.PLAN_APPROVED)
        raise HTTPException(status_code=502, detail="twilio dial failed") from exc

    runtime.mark_in_call()
    _persist_timestamps(session_id, runtime)
    session = set_state(session_id, SessionState.IN_CALL)
    await emit_state(session_id, session.state)
    start_live_ingest(session_id)

    if config.agent_leg_ready:
        try:
            add_agent_leg(client, config, runtime, status_url)
        except Exception:
            logger.warning(
                "agent leg failed session_id=%s; set TWILIO_AGENT_NUMBER + "
                "ELEVENLABS_* + PUBLIC_BASE_URL for Leg B",
                session_id,
                exc_info=True,
            )
    else:
        logger.warning(
            "agent leg skipped session_id=%s; need TWILIO_AGENT_NUMBER + "
            "ELEVENLABS_* + PUBLIC_BASE_URL for Leg B",
            session_id,
        )

    if config.token_ready:
        try:
            add_browser_leg(client, config, runtime, status_url)
        except Exception:
            logger.warning(
                "browser client not registered yet session_id=%s; "
                "Device.connect() can still join via /twilio/voice/browser",
                session_id,
                exc_info=True,
            )
    else:
        logger.info(
            "browser leg skipped session_id=%s (no TWILIO_TWIML_APP_SID)",
            session_id,
        )

    return {
        "session_id": session_id,
        "state": session.state.value,
        "conference": runtime.conference,
        "agent_call_sid": runtime.agent_call_sid,
    }


@router.post("/api/session/{session_id}/takeover")
async def takeover(session_id: str) -> dict:
    session = get_session(session_id)
    if session.state not in (SessionState.IN_CALL, SessionState.ESCALATING):
        raise HTTPException(
            status_code=409,
            detail=(
                f"illegal transition: state is {session.state.value}, "
                "expected IN_CALL or ESCALATING"
            ),
        )
    runtime = get_runtime(session_id)
    if runtime is None:
        raise HTTPException(status_code=409, detail="no live conference for session")

    config = load_config()
    if not config.rest_ready:
        raise HTTPException(
            status_code=503,
            detail="twilio rest not configured: missing TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN",
        )

    client = rest_client(config)
    try:
        unmute_browser(client, runtime)
    except Exception as exc:
        logger.exception("unmute failed session_id=%s", session_id)
        raise HTTPException(status_code=502, detail="twilio unmute failed") from exc
    hangup_agent(client, runtime)
    stop_live_ingest(session_id)

    unmuted_ts = runtime.mark_unmuted()
    _persist_timestamps(session_id, runtime)
    session = set_state(session_id, SessionState.HUMAN_CONTROL)
    await emit_event(
        session_id,
        "state_changed",
        {"state": session.state.value, **runtime.timestamp_data()},
    )
    return {
        "session_id": session_id,
        "state": session.state.value,
        "leg_c_unmuted_ts": unmuted_ts,
    }


@router.post("/twilio/voice/rep")
async def voice_rep(request: Request, session_id: str | None = None) -> Response:
    form = dict(await request.form())
    resolved = resolve_session_id(form, session_id)
    session = get_session_or_none(resolved) if resolved else None
    config = load_config()
    stream_url = config.media_stream_url(resolved) if resolved else None
    if resolved:
        start_live_ingest(resolved)
    logger.info(
        "rep twiml session_id=%s stream_url=%s",
        resolved,
        stream_url or "none",
    )
    return _xml(
        rep_twiml(
            session,
            stream_url=stream_url,
            session_id=resolved,
            stream_track="both_tracks",
        )
    )


@router.websocket("/twilio/media/{session_id}")
async def twilio_media(websocket: WebSocket, session_id: str) -> None:
    """Twilio Media Stream → ElevenLabs Scribe → policy gate."""
    await handle_twilio_media(websocket, session_id)


@router.post("/twilio/voice/browser")
async def voice_browser(request: Request, session_id: str | None = None) -> Response:
    form = dict(await request.form())
    resolved = resolve_session_id(form, session_id)
    if not resolved:
        raise HTTPException(status_code=400, detail="session_id required")
    get_session(resolved)
    config = load_config()
    return _xml(browser_twiml(resolved, status_url=config.status_url(resolved)))


@router.post("/twilio/voice/agent")
async def voice_agent(request: Request, session_id: str | None = None) -> Response:
    """Twilio Voice webhook for Leg B — ElevenLabs register_call TwiML."""
    form = {str(k): str(v) for k, v in (await request.form()).items()}
    resolved = resolve_session_id(form, session_id)
    if not resolved:
        raise HTTPException(status_code=400, detail="session_id required")
    session = get_session(resolved)
    config = load_config()

    from_number = _form_get(form, "From", "Caller") or config.caller_number
    to_number = (
        _form_get(form, "To", "Called")
        or config.agent_number
        or config.caller_number
    )
    if not from_number or not to_number:
        raise HTTPException(
            status_code=503,
            detail="twilio agent voice missing From/To and TWILIO_CALLER_NUMBER",
        )

    try:
        twiml = register_agent_call_twiml(
            session_id=resolved,
            from_number=from_number,
            to_number=to_number,
            session=session,
            direction="inbound",
        )
    except Exception:
        logger.exception("register_call failed session_id=%s", resolved)
        error = VoiceResponse()
        error.say(
            "Sorry — the automated assistant could not join this call.",
            voice="Polly.Joanna",
        )
        error.hangup()
        return _xml(str(error))

    call_sid = _form_get(form, "CallSid")
    runtime = get_runtime(resolved)
    if runtime is not None:
        if call_sid:
            remember_call_sid(runtime, "agent", call_sid)
        conversation_id = conversation_id_from_twiml(twiml)
        if conversation_id:
            runtime.conversation_id = conversation_id

    start_live_ingest(resolved)
    return _xml(twiml)


@router.post("/twilio/status")
async def twilio_status(request: Request, session_id: str | None = None) -> dict:
    form = {str(k): str(v) for k, v in (await request.form()).items()}
    resolved = resolve_session_id(form, session_id)
    if not resolved:
        logger.info("status with no session_id form=%s", form)
        return {"ok": True}

    session = get_session_or_none(resolved)
    if session is None:
        return {"ok": True}

    runtime = get_runtime(resolved)
    event = _form_get(
        form,
        "StatusCallbackEvent",
        "ConferenceStatusEvent",
        "CallStatus",
    ).lower()
    label = _form_get(form, "ParticipantLabel", "Label", "participant_label").lower()
    call_sid = _form_get(form, "CallSid")
    conference_sid = _form_get(form, "ConferenceSid")

    if runtime is not None:
        if conference_sid:
            runtime.conference_sid = conference_sid
        remember_call_sid(runtime, label, call_sid)

    logger.info(
        "twilio status session_id=%s event=%s label=%s state=%s",
        resolved,
        event,
        label,
        session.state.value,
    )

    if session.state in _ENDED_STATES:
        return {"ok": True}

    if session.state == SessionState.DIALING and _is_rep_live(event, label):
        if runtime is not None:
            runtime.mark_in_call()
            _persist_timestamps(resolved, runtime)
        session = set_state(resolved, SessionState.IN_CALL)
        await emit_state(resolved, session.state)
        start_live_ingest(resolved)
        return {"ok": True}

    if event in {"conference-end", "end", "completed", "busy", "no-answer", "failed", "canceled"}:
        if event in {"completed", "busy", "no-answer", "failed", "canceled"}:
            if runtime is not None and runtime.conference_sid:
                return {"ok": True}
        stop_live_ingest(resolved)
        if runtime is not None:
            runtime.mark_ended()
            _persist_timestamps(resolved, runtime)
            data = {"state": SessionState.ENDED.value, **runtime.timestamp_data()}
        else:
            data = {"state": SessionState.ENDED.value}
        set_state(resolved, SessionState.ENDED)
        await emit_event(resolved, "state_changed", data)
        await _emit_summary(resolved)

    return {"ok": True}


async def _emit_summary(session_id: str) -> None:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return
    session = get_session_or_none(session_id)
    if session is None or session.summary is not None:
        return
    try:
        summary = await generate_summary(session)
        session = set_summary(session_id, summary)
        await emit_event(session_id, "summary_ready", summary.model_dump())
        await emit_state(session_id, session.state)
    except Exception:
        logger.warning("auto-summary failed session_id=%s", session_id, exc_info=True)
